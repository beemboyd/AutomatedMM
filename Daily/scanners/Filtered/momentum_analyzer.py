#!/usr/bin/env python3
"""
Momentum Analyzer - Identifies Strong Momentum Candidates
Analyzes KC_Upper_Limit_Trending files to detect stocks showing:
1. Rapid rank improvement (40+ positions in hours)
2. Volume progression patterns
3. Score acceleration
4. 4-stage momentum progression
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import glob
import os
import json
import logging

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import reportlab, fall back to HTML if not available
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not available, will generate HTML report instead")


class MomentumAnalyzer:
    def __init__(self, lookback_days=3):
        self.lookback_days = lookback_days
        self.momentum_data = {}
        self.strong_candidates = []
        
        # Pattern thresholds based on analysis
        self.RAPID_RANK_THRESHOLD = 40  # positions improved
        self.RAPID_TIME_WINDOW = 48  # hours
        self.VOLUME_SURGE_THRESHOLD = 1.5  # minimum volume ratio for momentum
        self.SCORE_JUMP_THRESHOLD = 20  # score increase threshold
        self.TOP_RANK_THRESHOLD = 30  # must break into top 30
        
    def load_kc_files(self):
        """Load all KC_Upper_Limit_Trending files from the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)
        
        all_files = []
        current_date = start_date
        
        # Get base path relative to this script
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y%m%d')
            pattern = os.path.join(base_path, "results", f"KC_Upper_Limit_Trending_{date_str}_*.xlsx")
            files = glob.glob(pattern)
            all_files.extend(files)
            current_date += timedelta(days=1)
            
        # Sort files by timestamp
        all_files.sort()
        logger.info(f"Found {len(all_files)} KC files to analyze")
        return all_files
        
    def extract_file_datetime(self, filepath):
        """Extract datetime from filename"""
        filename = os.path.basename(filepath)
        parts = filename.split('_')
        date_str = parts[4]
        time_str = parts[5].replace('.xlsx', '')
        
        datetime_str = f"{date_str}{time_str}"
        return datetime.strptime(datetime_str, '%Y%m%d%H%M%S')
        
    def analyze_ticker_progression(self, ticker):
        """Analyze progression of a single ticker across all files"""
        if ticker not in self.momentum_data:
            return None
            
        data_points = self.momentum_data[ticker]
        if len(data_points) < 2:
            return None
            
        # Sort by timestamp
        data_points.sort(key=lambda x: x['timestamp'])
        
        # Calculate key metrics
        first_appearance = data_points[0]
        best_rank = min([d['rank'] for d in data_points])
        best_rank_data = next(d for d in data_points if d['rank'] == best_rank)
        
        # Rank improvement analysis
        rank_improvement = first_appearance['rank'] - best_rank
        time_to_best = (best_rank_data['timestamp'] - first_appearance['timestamp']).total_seconds() / 3600
        
        # Volume progression
        initial_volume = first_appearance.get('volume_ratio', 0)
        peak_volume = max([d.get('volume_ratio', 0) for d in data_points])
        
        # Score progression
        initial_score = first_appearance.get('score', 0)
        peak_score = max([d.get('score', 0) for d in data_points])
        score_jump = peak_score - initial_score
        
        # Determine momentum stage
        stage = self.classify_momentum_stage(best_rank, peak_volume, peak_score)
        
        # Check if it's a strong candidate
        is_strong_candidate = (
            rank_improvement >= self.RAPID_RANK_THRESHOLD and
            time_to_best <= self.RAPID_TIME_WINDOW and
            peak_volume >= self.VOLUME_SURGE_THRESHOLD and
            best_rank <= self.TOP_RANK_THRESHOLD and
            score_jump >= self.SCORE_JUMP_THRESHOLD
        )
        
        return {
            'ticker': ticker,
            'first_appearance': first_appearance['timestamp'],
            'initial_rank': first_appearance['rank'],
            'best_rank': best_rank,
            'rank_improvement': rank_improvement,
            'time_to_best_hours': round(time_to_best, 1),
            'initial_volume': round(initial_volume, 2),
            'peak_volume': round(peak_volume, 2),
            'volume_multiplier': round(peak_volume / initial_volume, 2) if initial_volume > 0 else 0,
            'initial_score': round(initial_score, 2),
            'peak_score': round(peak_score, 2),
            'score_jump': round(score_jump, 2),
            'current_stage': stage,
            'is_strong_candidate': is_strong_candidate,
            'latest_price': data_points[-1].get('price', 0),
            'price_change': round(((data_points[-1].get('price', 0) - first_appearance.get('price', 0)) / 
                                 first_appearance.get('price', 1)) * 100, 2) if first_appearance.get('price', 0) > 0 else 0,
            'appearances': len(data_points)
        }
        
    def classify_momentum_stage(self, rank, volume_ratio, score):
        """Classify ticker into momentum stage"""
        if rank <= 5 and score >= 90:
            return "Stage 4: Peak Momentum"
        elif rank <= 20 and score >= 70:
            return "Stage 3: Acceleration"
        elif rank <= 50 and score >= 30:
            return "Stage 2: Early Momentum"
        else:
            return "Stage 1: Accumulation"
            
    def process_all_files(self):
        """Process all KC files and build momentum database"""
        files = self.load_kc_files()
        
        for filepath in files:
            try:
                df = pd.read_excel(filepath)
                timestamp = self.extract_file_datetime(filepath)
                
                # Process each ticker in the file
                for idx, row in df.iterrows():
                    ticker = row.get('Ticker', row.get('Symbol', ''))
                    if not ticker:
                        continue
                        
                    if ticker not in self.momentum_data:
                        self.momentum_data[ticker] = []
                        
                    # Extract relevant data - handle different column names
                    data_point = {
                        'timestamp': timestamp,
                        'rank': idx + 1,  # Rank based on position in file
                        'score': row.get('Probability_Score', row.get('Score', row.get('Probability', 0))),
                        'volume_ratio': row.get('Volume_Ratio', row.get('Vol_Ratio', 0)),
                        'price': row.get('Entry_Price', row.get('Close', row.get('Price', 0))),
                        'adx': row.get('ADX', 0),
                        'momentum_5d': row.get('Momentum_5D', row.get('Momentum_5d', 0)),
                        'momentum_10d': row.get('Momentum_10D', row.get('Momentum_10d', 0))
                    }
                    
                    self.momentum_data[ticker].append(data_point)
                    
            except Exception as e:
                logger.error(f"Error processing file {filepath}: {str(e)}")
                continue
                
    def identify_strong_candidates(self):
        """Identify all strong momentum candidates"""
        logger.info("Analyzing ticker progressions...")
        
        for ticker in self.momentum_data:
            analysis = self.analyze_ticker_progression(ticker)
            if analysis and analysis['is_strong_candidate']:
                self.strong_candidates.append(analysis)
                
        # Sort by rank improvement
        self.strong_candidates.sort(key=lambda x: x['rank_improvement'], reverse=True)
        logger.info(f"Identified {len(self.strong_candidates)} strong momentum candidates")
        
    def generate_html_report(self):
        """Generate HTML report of strong candidates"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output directory structure if needed
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_path, "results", "StrongM", "HTML")
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"Strong_Candidates_{timestamp}.html")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Strong Momentum Candidates Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    text-align: center;
                    color: #2C3E50;
                    margin-bottom: 30px;
                }}
                .metadata {{
                    color: #7F8C8D;
                    margin-bottom: 20px;
                }}
                .criteria {{
                    background-color: #ECF0F1;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 30px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    background-color: white;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                th {{
                    background-color: #3498DB;
                    color: white;
                    padding: 12px;
                    text-align: center;
                    font-weight: bold;
                }}
                td {{
                    padding: 10px;
                    text-align: center;
                    border-bottom: 1px solid #ddd;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .stage-1 {{ color: #95A5A6; }}
                .stage-2 {{ color: #F39C12; }}
                .stage-3 {{ color: #E67E22; }}
                .stage-4 {{ color: #E74C3C; font-weight: bold; }}
                .positive {{ color: #27AE60; }}
                .negative {{ color: #E74C3C; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Strong Momentum Candidates Report</h1>
            </div>
            
            <div class="metadata">
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Analysis Period: Last {self.lookback_days} days</p>
                <p>Total Candidates: {len(self.strong_candidates)}</p>
            </div>
            
            <div class="criteria">
                <h3>Selection Criteria:</h3>
                <ul>
                    <li>Rank improvement: 40+ positions within 48 hours</li>
                    <li>Volume surge: Peak volume > 1.5x initial</li>
                    <li>Score acceleration: 20+ point increase</li>
                    <li>Must break into Top 30 rankings</li>
                </ul>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Stage</th>
                        <th>Rank Progress</th>
                        <th>Time (hrs)</th>
                        <th>Volume Progression</th>
                        <th>Score Jump</th>
                        <th>Price Change</th>
                        <th>Latest Price</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for candidate in self.strong_candidates[:20]:
            stage_num = candidate['current_stage'].split(' ')[1].replace(':', '')
            stage_class = f"stage-{stage_num}"
            price_class = "positive" if candidate['price_change'] > 0 else "negative"
            
            html_content += f"""
                    <tr>
                        <td><strong>{candidate['ticker']}</strong></td>
                        <td class="{stage_class}">{candidate['current_stage'].split(':')[1].strip()}</td>
                        <td>{candidate['initial_rank']} &rarr; {candidate['best_rank']}<br>({candidate['rank_improvement']}&uarr;)</td>
                        <td>{candidate['time_to_best_hours']}</td>
                        <td>{candidate['initial_volume']}x &rarr; {candidate['peak_volume']}x<br>({candidate['volume_multiplier']}x)</td>
                        <td>{candidate['initial_score']} &rarr; {candidate['peak_score']}<br>(+{candidate['score_jump']})</td>
                        <td class="{price_class}">{candidate['price_change']:+.1f}%</td>
                        <td>&#8377;{candidate['latest_price']:,.0f}</td>
                    </tr>
            """
            
        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        with open(output_path, 'w') as f:
            f.write(html_content)
            
        logger.info(f"HTML report generated: {output_path}")
        return output_path
    
    def generate_pdf_report(self):
        """Generate PDF report of strong candidates"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create output directory structure if needed
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_path, "results", "StrongM", "PDF")
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"Strong_Candidates_{timestamp}.pdf")
        
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph("Strong Momentum Candidates Report", title_style))
        elements.append(Spacer(1, 20))
        
        # Report metadata
        metadata_style = ParagraphStyle(
            'Metadata',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#7F8C8D')
        )
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", metadata_style))
        elements.append(Paragraph(f"Analysis Period: Last {self.lookback_days} days", metadata_style))
        elements.append(Paragraph(f"Total Candidates: {len(self.strong_candidates)}", metadata_style))
        elements.append(Spacer(1, 20))
        
        # Pattern criteria
        criteria_style = ParagraphStyle(
            'Criteria',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#34495E')
        )
        elements.append(Paragraph("<b>Selection Criteria:</b>", criteria_style))
        elements.append(Paragraph("• Rank improvement: 40+ positions within 48 hours", criteria_style))
        elements.append(Paragraph("• Volume surge: Peak volume > 1.5x initial", criteria_style))
        elements.append(Paragraph("• Score acceleration: 20+ point increase", criteria_style))
        elements.append(Paragraph("• Must break into Top 30 rankings", criteria_style))
        elements.append(Spacer(1, 30))
        
        # Create table data
        if self.strong_candidates:
            # Table headers
            headers = [
                'Ticker', 'Stage', 'Rank\nProgress', 'Time\n(hrs)', 
                'Volume\nProgression', 'Score\nJump', 'Price\nChange', 'Latest\nPrice'
            ]
            
            table_data = [headers]
            
            # Add candidate data
            for candidate in self.strong_candidates[:20]:  # Top 20 candidates
                row = [
                    candidate['ticker'],
                    candidate['current_stage'].replace('Stage ', '').split(':')[0],
                    f"{candidate['initial_rank']}→{candidate['best_rank']}\n({candidate['rank_improvement']}↑)",
                    str(candidate['time_to_best_hours']),
                    f"{candidate['initial_volume']}x→{candidate['peak_volume']}x\n({candidate['volume_multiplier']}x)",
                    f"{candidate['initial_score']}→{candidate['peak_score']}\n(+{candidate['score_jump']})",
                    f"{candidate['price_change']:+.1f}%",
                    f"₹{candidate['latest_price']:,.0f}"
                ]
                table_data.append(row)
                
            # Create table
            table = Table(table_data, colWidths=[1.2*inch, 0.8*inch, 1.2*inch, 0.8*inch, 
                                                1.5*inch, 1.2*inch, 1*inch, 1*inch])
            
            # Style the table
            table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Data styling
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Alternate row coloring
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
                
                # Stage column color coding
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#E74C3C')),
            ]))
            
            elements.append(table)
            
        else:
            elements.append(Paragraph("No strong momentum candidates found in the analysis period.", styles['Normal']))
            
        # Build PDF
        doc.build(elements)
        logger.info(f"Report generated: {output_path}")
        return output_path
        
    def run_analysis(self):
        """Run complete momentum analysis"""
        logger.info("Starting momentum analysis...")
        
        # Process all files
        self.process_all_files()
        
        # Identify strong candidates
        self.identify_strong_candidates()
        
        # Generate report (PDF if available, else HTML)
        if REPORTLAB_AVAILABLE:
            report_path = self.generate_pdf_report()
        else:
            report_path = self.generate_html_report()
        
        # Also save as JSON for further processing
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        json_dir = os.path.join(base_path, "results", "StrongM", "JSON")
        os.makedirs(json_dir, exist_ok=True)
        json_path = os.path.join(json_dir, f"Strong_Candidates_{timestamp}.json")
        
        with open(json_path, 'w') as f:
            json.dump(self.strong_candidates, f, indent=2, default=str)
            
        logger.info(f"Analysis complete. Found {len(self.strong_candidates)} strong candidates.")
        return report_path

if __name__ == "__main__":
    analyzer = MomentumAnalyzer(lookback_days=3)
    report_path = analyzer.run_analysis()
    print(f"Strong candidates report generated: {report_path}")