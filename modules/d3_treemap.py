import json
import pandas as pd
import streamlit as st

def generate_d3_treemap_v4(df_pivot, port_name="Portfolio"):
    """
    Generates a D3.js Treemap HTML string for a specific portfolio.
    
    Args:
        df_pivot (pd.DataFrame): Data containing '종목', '평가금액', 'ReturnRate', etc.
        port_name (str): Name of the portfolio (root node).
        
    Returns:
        str: HTML string to be rendered with components.html
    """
    
    if df_pivot.empty:
        return "<div>No Data</div>"

    # 1. Prepare Data for D3 (Hierarchical JSON)
    # Structure: { name: "Root", children: [ {name: "Ticker", value: 100, rate: 5.5, ...}, ... ] }
    
    children = []
    for _, row in df_pivot.iterrows():
        # Get color-driving value
        rate = row.get('ReturnRate', 0)
        value = row.get('평가금액', 0)
        
        # Color Logic (Same as Plotly: -30 to +30 range mapping to Red-Green)
        # We will handle color calculation in JS or pass raw rate. 
        # Passing raw rate is better for tooltip.
        
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
    # We use a responsive container.
    # IMPORTANT: Since this is an f-string, all JS curly braces must be DOUBLED {{ }}
    # Only {json_data} uses single braces.
    
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
                /* Text Shadow for better contrast */
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
                font-size: 14px;
                background: rgba(30, 30, 30, 0.9);
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                pointer-events: none;
                z-index: 10;
                opacity: 0;
                transition: opacity 0.2s;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }}
        </style>
        <script src="https://d3js.org/d3.v7.min.js"></script>
    </head>
    <body>
        <div id="chart"></div>
        <div class="tooltip" id="tooltip"></div>

        <script>
            const data = {json_data};
            
            // Finviz Style Color Scale
            // -3% (Red) to +3% (Green)
            const colorScale = d3.scaleLinear()
                .domain([-30, 0, 30])
                .range(["#f63538", "#303030", "#30cc5a"])
                .clamp(true);

            function drawChart() {{
                const container = document.getElementById('chart');
                const width = container.clientWidth;
                const height = container.clientHeight;

                container.innerHTML = ''; // Clear previous

                // Hierarchical Data
                const root = d3.hierarchy(data)
                    .sum(d => d.value)
                    .sort((a, b) => b.value - a.value);

                // Treemap Layout
                d3.treemap()
                    .size([width, height])
                    .paddingInner(1) // Thin border
                    .paddingOuter(0)
                    .round(true)
                    (root);

                const svg = d3.select("#chart").append("svg")
                    .attr("width", width)
                    .attr("height", height);

                // Nodes
                const nodes = svg.selectAll("g")
                    .data(root.leaves())
                    .enter().append("g")
                    .attr("transform", d => `translate(${{d.x0}},${{d.y0}})`);

                // Rects
                nodes.append("rect")
                    .attr("width", d => Math.max(0, d.x1 - d.x0))
                    .attr("height", d => Math.max(0, d.y1 - d.y0))
                    .attr("fill", d => colorScale(d.data.rate))
                    // Tooltip Events
                    .on("mouseover", function(event, d) {{
                        const tt = d3.select("#tooltip");
                        tt.style("opacity", 1);
                        tt.html(`
                            <span style='font-size:16px; font-weight:bold'>${{d.data.name}}</span><br>
                            <span style='font-size:11px; color:#cccccc'>${{d.data.qty.toLocaleString()}}주 보유</span><br><br>
                            
                            <span style='color:#aaaaaa'>평가금액:</span> <b style='font-size:15px'>${{d.data.symbol}}${{d.data.value.toLocaleString()}}</b> 
                            <span style='font-size:13px'>(${{d.data.rate > 0 ? '+' : ''}}${{d.data.rate.toFixed(2)}}%)</span><br>
                            
                            <span style='color:#aaaaaa'>매입금액:</span> <b>${{d.data.symbol}}${{d.data.invested.toLocaleString()}}</b><br>
                            <span style='color:#aaaaaa'>총 손 익:</span> <b>${{d.data.symbol}}${{d.data.profit.toLocaleString()}}</b><br><br>
                            
                            <span style='color:#aaaaaa'>현 재 가:</span> ${{d.data.symbol}}${{d.data.price.toLocaleString()}}<br>
                            <span style='color:#aaaaaa'>평 단 가:</span> ${{d.data.symbol}}${{d.data.avg_price.toLocaleString()}}<br><br>
                            
                            <span style='font-size:10px; color:#888888'>배당금 ${{d.data.symbol}}${{d.data.dividend.toLocaleString()}} | 실현손익 ${{d.data.symbol}}${{d.data.realized.toLocaleString()}}</span>
                        `);
                    }})
                    .on("mousemove", function(event) {{
                        const tt = d3.select("#tooltip");
                        const tooltipNode = tt.node();
                        const tooltipWidth = tooltipNode.offsetWidth || 220; 
                        const tooltipHeight = tooltipNode.offsetHeight || 280;
                        
                        const windowWidth = window.innerWidth;
                        const windowHeight = window.innerHeight;
                        
                        // Default: Right-Down
                        let leftPos = event.pageX + 15;
                        let topPos = event.pageY + 15;
                        
                        // 1. Horizontal Flip (Right Edge)
                        if (event.clientX + tooltipWidth + 30 > windowWidth) {{
                            leftPos = event.pageX - tooltipWidth - 20;
                        }}
                        
                        // 2. Vertical Flip (Bottom Edge)
                        // If tooltip hits bottom, flip UP
                        if (event.clientY + tooltipHeight + 30 > windowHeight) {{
                             topPos = event.pageY - tooltipHeight - 10;
                        }}
                        
                        tt.style("left", leftPos + "px")
                          .style("top", topPos + "px");
                    }})
                    .on("mouseout", function() {{
                        d3.select("#tooltip").style("opacity", 0);
                    }});

                // --- Text Fitting Logic (Robust) ---
                nodes.each(function(d) {{
                    const g = d3.select(this);
                    const w = d.x1 - d.x0;
                    const h = d.y1 - d.y0;
                    
                    if (w < 20 || h < 20) return; // Skip tiny nodes

                    // 1. Ticker Name (Bold)
                    const tickerText = g.append("text")
                        .attr("class", "node-label")
                        .text(d.data.name)
                        .attr("x", w / 2)
                        .attr("y", h / 2); // Start centered

                    // Initial font size estimation (aggressive)
                    let fontSize = Math.min(w / 3, h / 3, 60);
                    if (fontSize < 12) fontSize = 12;

                    tickerText.style("font-size", fontSize + "px");

                    // Refine size based on actual width (Iterative Loop)
                    let textWidth = tickerText.node().getComputedTextLength();
                    const padding = 10;
                    const minFontSize = 10;

                    // Reduce font size until it fits
                    while (textWidth > w - padding && fontSize > minFontSize) {{
                        fontSize -= 1; // Decrement by 1px
                        tickerText.style("font-size", fontSize + "px");
                        textWidth = tickerText.node().getComputedTextLength();
                    }}
                    
                    // Final check
                    if (textWidth > w - 2) {{
                       // Pass
                    }}

                    // Re-measure after resize (approximated)
                    // Apply offset for vertical centering relative to Subtext
                    
                    const hasSub = fontSize >= 14; 
                    const yOffset = hasSub ? -fontSize * 0.2 : 0;
                    tickerText.attr("y", (h / 2) + yOffset);

                    // 2. Return Rate (Subtext)
                    if (hasSub) {{
                        const rateStr = d.data.rate > 0 ? "+" + d.data.rate.toFixed(2) + "%" : d.data.rate.toFixed(2) + "%";
                        
                        // Subtext defaults to 60% of ticker size
                        let subSize = fontSize * 0.6;
                        const subText = g.append("text")
                            .attr("class", "node-sub")
                            .attr("x", w / 2)
                            .attr("y", (h / 2) + (fontSize * 0.8) + yOffset)
                            .text(rateStr)
                            .style("font-size", subSize + "px");
                        
                        // Check subtext width too
                        let subWidth = subText.node().getComputedTextLength();
                        
                        // Reduce subtext size loop
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
