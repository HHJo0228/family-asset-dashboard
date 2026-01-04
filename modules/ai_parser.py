import google.generativeai as genai
import streamlit as st
import json
import pandas as pd
from datetime import datetime

def configure_genai():
    """Configures Gemini API using streamlit secrets."""
    try:
        api_key = st.secrets["general"]["gemini_api_key"]
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False

def parse_transaction_image(image_data_list):
    """
    Sends images to Gemini Flash and retrieves structured transaction data.
    Args:
        image_data_list: List of image bytes (or single bytes object)
    Returns: List of dicts or None
    """
    if not configure_genai():
        return "API_KEY_MISSING"

    # 'gemini-1.5-flash' not found for this user. 
    # Available: gemini-2.0-flash, gemini-2.5-flash, gemini-flash-latest
    # Using 'gemini-2.0-flash' for high performance and stability.
    model = genai.GenerativeModel('gemini-2.0-flash')

    # Ensure input is a list
    if not isinstance(image_data_list, list):
        image_data_list = [image_data_list]

    # Construct Content Parts
    # Prompt + Image1 + Image2 + ...
    prompt_text = """
    Analyze these images (Sequential MTS trading screenshots).
    Stitch the information together if it spans multiple images (e.g. long list).
    Extract ALL transaction details into a JSON List.
    
    Fields required:
    - account_number: Extract "Account Number" from the top header (e.g., 6459-6247). Output same value for all rows.
    - date: "YYYY-MM-DD" (If year is missing, assume 2025. If context implies otherwise, use judgment.)
    - type: Strict Mapping required. Must be one of ["매수", "매도", "배당금", "배당세", "이자", "입금", "출금", "환전", "확정손익"].
      - "Buy", "장내매수", "현금매수" -> "매수".
      - "Sell", "장내매도", "현금매도" -> "매도".
      - "Div" -> "배당금".
      - "현지배당세출금", "배당세" -> "배당세".
      - IMPORTANT: If description (적요) or details contain "배당" (e.g. "배당금입금", "배당금(외화)입금"), MUST classify as "배당금", NOT "입금".
    - ticker: "The Ticker Symbol (e.g. TSLA, 005930, SPY). STRICTLY PREFER the alphanumeric Ticker over the detailed Stock Name. If the image contains both 'TIP' and '미국물가채...', extract 'TIP'. Only return the Stock Name if NO ticker is visible."
    - price: Unit price (numeric)
    - qty: Quantity (numeric)
    - amount: Settlement Amount (정산금액) PREFERRED.
      - If "Pending" (Order), use (Price * Qty) or Execution Amount.
      - If "Settled" (Statement), use Net Settlement Amount (Fees/Tax deducted).
    - currency: "$" or "₩" (Infer from context)
    - note: "Pending" or "Settled" (MANDATORY FIELD)
      - "Pending": If Header contains "주문내역", "체결내역", "미체결" or column has "주문".
      - "Settled": If Header contains "거래내역", "입출금", "자산", "정산" or type is "입금/출금/배당".
      - If unsure, Check Columns:
        - "체결가", "미체결", "주문" columns present -> "Pending"
        - "정산금액", "수수료", "거래세" columns present -> "Settled"
      - Default to "Settled" only if strong evidence lacks.
    
    Rules:
    - **CRITICAL**: Check the Image Header AND Table Columns.
      - "주문내역" OR Column "체결가" -> "Pending".
      - "거래내역" OR Column "정산금액" -> "Settled".
    - Ignore failed/cancelled transactions.
    - If a row is cut off between images, try to reconstruct it or get most complete.
    - Return ONLY raw JSON string.
    """
    
    content_parts = [prompt_text]
    for img_bytes in image_data_list:
        content_parts.append({'mime_type': 'image/jpeg', 'data': img_bytes})

    import time
    import random
    
    max_retries = 3
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            response = model.generate_content(content_parts)
            
            # Clean response (sometimes has ```json ... ```)
            text = response.text.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                return None
                
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if retry_count == max_retries:
                    st.error(f"AI Limit Reached (429). Please try again later. Details: {e}")
                    return None
                
                # Semantic Backoff: 2s -> 4s -> 8s + Jitter
                sleep_time = (2 ** (retry_count + 1)) + random.uniform(0, 1)
                st.toast(f"AI Busy... Retrying in {int(sleep_time)}s ⏳", icon="⚠️")
                time.sleep(sleep_time)
                retry_count += 1
            else:
                st.error(f"AI Parse Error: {e}")
                return None
