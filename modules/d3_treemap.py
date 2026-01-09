import json
import pandas as pd
import streamlit as st

def generate_d3_treemap_v6(df_pivot, port_name="Portfolio"):
    """
    Generates a D3.js Treemap HTML string for a specific portfolio.
    v6: Selective Currency Symbols (Prices in $, Values in ₩).
    
    Args:
        df_pivot (pd.DataFrame): Data containing '종목', '평가금액', 'ReturnRate', etc.
        port_name (str): Name of the portfolio (root node).
        
    Returns:
        str: HTML string to be rendered with components.html
    """
    
    if df_pivot.empty:
        return "<div>No Data</div>"

    # 1. Prepare Data for D3 (Hierarchical JSON)
    children = []
    for _, row in df_pivot.iterrows():
        rate = row.get('ReturnRate', 0)
        value = row.get('평가금액', 0)
        
        child = {
            "name": str(row['종목']),
            "value": float(value),
            "rate": float(rate),
            "price": float(row.get('현재가', 0)),
            "profit": float(row.get('총평가손익', 0)),
            "invested": float(row.get('매입금액', 0)),
            "qty": float(row.get('보유주수', 0)),
            "avg_price": float(row.get('평단가', 0)),
            "dividend": float(row.get('배당수익', 0)),
            "realized": float(row.get('확정손익', 0)),
            "symbol": row.get('CurSymbol', '₩') 
        }
        children.append(child)
        
    data_tree = {
        "name": port_name,
        "children": children
    }
    
    json_data = json.dumps(data_tree)

    # 2. HTML/JS Template
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; background-color: transparent; font-family: 'SUIT', sans-serif; }}
            #chart {{ width: 100vw; height: 500px; }}
            .node {{ box-sizing: border-box; position: absolute; overflow: hidden; border: 1px solid #1e1e1e; cursor: default; }}
            .node-label {{ 
                position: absolute; 
                fill: white; 
                text-anchor: middle; 
                dominant-baseline: central; 
                pointer-events: none;
                font-family: 'SUIT', sans-serif;
                font-weight: 700;
                text-shadow: 0px 0px 3px rgba(0,0,0,0.8);
            }}
            .node-sub {{ 
                position: absolute; 
                fill: white; 
                text-anchor: middle; 
                dominant-baseline: central; 
                pointer-events: none;
                font-family: 'SUIT', sans-serif;
                font-weight: 400;
                opacity: 0.9;
                text-shadow: 0px 0px 2px rgba(0,0,0,0.8);
            }}
            /* Tooltip */
            .tooltip {{
                position: absolute;
                text-align: left;
                padding: 10px;
                background: rgba(30, 30, 30, 0.95);
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                pointer-events: none;
                z-index: 10;
                opacity: 0;
                transition: opacity 0.15s;
                box-shadow: 0 4px 8px rgba(0,0,0,0.4);
            }}
        </style>
        <script src="https://d3js.org/d3.v7.min.js"></script>
    </head>
    <body>
        <div id="chart"></div>
        <div class="tooltip" id="tooltip"></div>

        <script>
            const data = {json_data};
            
            const colorScale = d3.scaleLinear()
                .domain([-30, 0, 30])
                .range(["#f63538", "#303030", "#30cc5a"])
                .clamp(true);

            function drawChart() {{
                const container = document.getElementById('chart');
                const width = container.clientWidth;
                const height = container.clientHeight;

                container.innerHTML = ''; 

                const root = d3.hierarchy(data)
                    .sum(d => d.value)
                    .sort((a, b) => b.value - a.value);

                d3.treemap()
                    .size([width, height])
                    .paddingInner(1)
                    .paddingOuter(0)
                    .round(true)
                    (root);

                const svg = d3.select("#chart").append("svg")
                    .attr("width", width)
                    .attr("height", height);

                const nodes = svg.selectAll("g")
                    .data(root.leaves())
                    .enter().append("g")
                    .attr("transform", d => `translate(${{d.x0}},${{d.y0}})`);

                nodes.append("rect")
                    .attr("width", d => Math.max(0, d.x1 - d.x0))
                    .attr("height", d => Math.max(0, d.y1 - d.y0))
                    .attr("fill", d => colorScale(d.data.rate))
                    // --- MOUSE OVER: Dynamic Content Sizing ---
                    .on("mouseover", function(event, d) {{
                        const tt = d3.select("#tooltip");
                        tt.style("opacity", 1);
                        
                        // Check Screen Width for Compact Mode
                        const isSmall = window.innerWidth < 600;
                        
                        // Define Styles based on mode
                        const sTitle = isSmall ? 'font-size:13px; font-weight:bold' : 'font-size:16px; font-weight:bold';
                        const sSub = isSmall ? 'font-size:10px; color:#cccccc' : 'font-size:11px; color:#cccccc';
                        const sLabel = isSmall ? 'font-size:11px; color:#cccccc' : 'color:#aaaaaa';
                        const sVal = isSmall ? 'font-size:12px' : 'font-size:15px';
                        const sPct = isSmall ? 'font-size:11px' : 'font-size:13px';
                        const sFooter = isSmall ? 'font-size:9px; color:#888888' : 'font-size:10px; color:#888888';
                        
                        const pad = isSmall ? '4px' : '10px';
                        tt.style("padding", pad);

                        // CURRENCY LOGIC: v6 Update
                        // Values in KRW (Inventory converted) -> Hardcode '₩'
                        // Prices in Native Currency -> Use d.data.symbol ($ or ₩)
                        
                        tt.html(`
                            <span style='${{sTitle}}'>${{d.data.name}}</span><br>
                            <span style='${{sSub}}'>${{d.data.qty.toLocaleString()}}주 보유</span><br><br>
                            
                            <span style='${{sLabel}}'>평가금액:</span> <b style='${{sVal}}'>₩${{d.data.value.toLocaleString()}}</b> 
                            <span style='${{sPct}}'>(${{d.data.rate > 0 ? '+' : ''}}${{d.data.rate.toFixed(2)}}%)</span><br>
                            
                            <span style='${{sLabel}}'>매입금액:</span> <b>₩${{d.data.invested.toLocaleString()}}</b><br>
                            <span style='${{sLabel}}'>총 손 익:</span> <b>₩${{d.data.profit.toLocaleString()}}</b><br><br>
                            
                            <span style='${{sLabel}}'>현 재 가:</span> ${{d.data.symbol}}${{d.data.price.toLocaleString()}}<br>
                            <span style='${{sLabel}}'>평 단 가:</span> ${{d.data.symbol}}${{d.data.avg_price.toLocaleString()}}<br><br>
                            
                            <span style='${{sFooter}}'>배당금 ₩${{d.data.dividend.toLocaleString()}} | 실현손익 ₩${{d.data.realized.toLocaleString()}}</span>
                        `);
                    }})
                    .on("mousemove", function(event) {{
                        const tt = d3.select("#tooltip");
                        const tooltipNode = tt.node();
                        const tooltipWidth = tooltipNode.offsetWidth || 150; 
                        const tooltipHeight = tooltipNode.offsetHeight || 200;
                        
                        const windowWidth = window.innerWidth;
                        const windowHeight = window.innerHeight;
                        
                        let leftPos = event.pageX + 15;
                        let topPos = event.pageY + 15;
                        
                        if (event.clientX + tooltipWidth + 30 > windowWidth) {{
                            leftPos = event.pageX - tooltipWidth - 20;
                        }}
                        
                        if (event.clientY + tooltipHeight + 30 > windowHeight) {{
                             topPos = event.pageY - tooltipHeight - 10;
                        }}
                        
                        tt.style("left", leftPos + "px")
                          .style("top", topPos + "px");
                    }})
                    .on("mouseout", function() {{
                        d3.select("#tooltip").style("opacity", 0);
                    }});

                nodes.each(function(d) {{
                    const g = d3.select(this);
                    const w = d.x1 - d.x0;
                    const h = d.y1 - d.y0;
                    
                    if (w < 20 || h < 20) return; 

                    const tickerText = g.append("text")
                        .attr("class", "node-label")
                        .text(d.data.name)
                        .attr("x", w / 2)
                        .attr("y", h / 2); 

                    let fontSize = Math.min(w / 3, h / 3, 60);
                    if (fontSize < 12) fontSize = 12;
                    tickerText.style("font-size", fontSize + "px");

                    let textWidth = tickerText.node().getComputedTextLength();
                    const padding = 10;
                    const minFontSize = 10;

                    while (textWidth > w - padding && fontSize > minFontSize) {{
                        fontSize -= 1; 
                        tickerText.style("font-size", fontSize + "px");
                        textWidth = tickerText.node().getComputedTextLength();
                    }}
                    
                    const hasSub = fontSize >= 14; 
                    const yOffset = hasSub ? -fontSize * 0.2 : 0;
                    tickerText.attr("y", (h / 2) + yOffset);

                    if (hasSub) {{
                        const rateStr = d.data.rate > 0 ? "+" + d.data.rate.toFixed(2) + "%" : d.data.rate.toFixed(2) + "%";
                        let subSize = fontSize * 0.6;
                        const subText = g.append("text")
                            .attr("class", "node-sub")
                            .attr("x", w / 2)
                            .attr("y", (h / 2) + (fontSize * 0.8) + yOffset)
                            .text(rateStr)
                            .style("font-size", subSize + "px");
                        
                        let subWidth = subText.node().getComputedTextLength();
                        while (subWidth > w - padding && subSize > 8) {{
                             subSize -= 1;
                             subText.style("font-size", subSize + "px");
                             subWidth = subText.node().getComputedTextLength();
                        }}
                    }}
                }});
            }}

            drawChart();
            window.addEventListener('resize', drawChart);
        </script>
    </body>
    </html>
    """
    return html_content
