#!/usr/bin/env python3
"""
Extract vessel table from PDF and convert to CSV
"""

import requests
from bs4 import BeautifulSoup
import PyPDF2
import csv
import os
import re
import time
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class PDFExtractor:
    def __init__(self, project_dir=PROJECT_DIR):
        self.base_url = "https://cpa.gov.bd"
        self.project_dir = project_dir
        self.csv_file = os.path.join(project_dir, "vessels_data.csv")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session.verify = False

        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _fetch_with_retries(self, url, timeout=60, attempts=3):
        """GET a URL with retries/backoff - the CPA site is slow and flaky."""
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                logger.info(f"🌐 Fetching {url.split('?')[0]} (attempt {attempt}/{attempts})...")
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️  Attempt {attempt}/{attempts} failed: {str(e)}")
                if attempt < attempts:
                    wait = 10 * attempt
                    logger.info(f"⏳ Retrying in {wait}s...")
                    time.sleep(wait)
        raise last_error if last_error else RuntimeError("Request failed")

    def get_latest_pdf(self):
        """Get the newest vessel PDFs from the CPA website"""
        try:
            logger.info("🔍 Fetching latest PDF from CPA website...")

            # The vessel-information documents are filed under 'Berthing-Schedule'.
            # Fetch the unfiltered listing (server-rendered rows) and collect the
            # newest rows that carry a vessel PDF - more robust than relying on
            # the Bengali search query.
            url = "https://cpa.gov.bd/pages/common-documents/?page=1&page_size=50"

            response = self._fetch_with_retries(url, timeout=60, attempts=3)

            soup = BeautifulSoup(response.content, 'html.parser')
            table_rows = soup.find_all('tr')

            if not table_rows:
                logger.warning("No documents found")
                return None

            candidates = []

            for row in table_rows:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                doctype = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                title = cells[1].get_text(strip=True) if len(cells) > 1 else ''

                # Only vessel lineup docs (doctype Berthing-Schedule / Vessels-Particulars,
                # or a Bengali title mentioning vessel info)
                is_vessel_doc = (
                    doctype.lower() in ('berthing-schedule', 'vessels-particulars')
                    or 'জাহাজ' in title
                )

                link = row.find('a', href=True)
                if not (link and '.pdf' in link.get('href', '').lower()):
                    continue

                pdf_url = link.get('href')
                if not pdf_url.startswith('http'):
                    pdf_url = self.base_url + pdf_url

                if not is_vessel_doc:
                    # The listing is newest-first; once we have seen vessel docs,
                    # older non-vessel rows can be ignored.
                    if candidates:
                        break
                    continue

                candidates.append({
                    'url': pdf_url,
                    'filename': os.path.basename(pdf_url.split('?')[0]),
                    'title': title or 'vessel_data'
                })

            if not candidates:
                logger.warning("No vessel PDFs found in listing")
                return None

            return candidates

        except Exception as e:
            logger.error(f"Error fetching PDF: {str(e)}")
            return None

    def _pdf_dated(self, pdf_path):
        """Read the DATED: line from a CPA PDF's first page (DD/MM/YYYY)."""
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = reader.pages[0].extract_text() or ''
            m = re.search(r'DATED:\s*(\d{1,2}/\d{1,2}/\d{4})', text, re.IGNORECASE)
            if m:
                return datetime.strptime(m.group(1), '%d/%m/%Y')
        except Exception as e:
            logger.debug(f"Could not read DATED from {pdf_path}: {str(e)}")
        return None

    def _is_vessel_lineup(self, pdf_path):
        """True if this PDF is the daily vessel declaration lineup (not the
        berthing-position sheet CPA also files under 'Berthing-Schedule')."""
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = (reader.pages[0].extract_text() or '') if reader.pages else ''
            upper = text.upper()
            if 'BERTHING POSITION' in upper or 'PERFORMANCE' in upper:
                return False
            return (
                'LIST OF VESSELS' in upper
                or 'VESSELS DUE' in upper
                or 'VESSELS READY' in upper
                or 'VESSELS NOT READY' in upper
                or 'TANKER DUE' in upper
                or 'AWAITING' in upper
            )
        except Exception as e:
            logger.debug(f"Could not classify {pdf_path}: {str(e)}")
            return False

    def download_pdf(self, pdf_info):
        """Download PDF file"""
        try:
            filepath = os.path.join(self.project_dir, pdf_info['filename'])

            if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                logger.info(f"✓ PDF already exists: {pdf_info['filename']}")
                return filepath

            logger.info(f"📥 Downloading: {pdf_info['filename']}")

            response = self._fetch_with_retries(pdf_info['url'], timeout=90, attempts=3)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            if not response.content.startswith(b'%PDF'):
                logger.error(f"❌ Downloaded file is not a valid PDF: {pdf_info['filename']}")
                os.remove(filepath)
                return None

            logger.info(f"✅ Downloaded: {pdf_info['filename']}")
            return filepath

        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            return None

    def extract_table_from_pdf(self, pdf_path):
        """Extract vessel table from PDF"""
        try:
            logger.info("📄 Extracting table from PDF...")

            vessels = []
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)

                current_section = 'Outer Anchorage'

                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()

                    lines = text.split('\n')
                    for line in lines:
                        current_section = self._section_from_line(line, current_section)
                        vessel = self._parse_vessel_line(line, current_section)
                        if vessel:
                            vessels.append(vessel)

            logger.info(f"✅ Extracted {len(vessels)} vessels from PDF")
            return vessels

        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            return []

    def _is_vessel_line(self, line):
        """Check if line contains vessel data"""
        return bool(re.match(r'^\s*\d+\s+', line)) and len(line) > 20

    def _section_from_line(self, line, current_section):
        """Track the CPA section heading so each parsed row gets a useful status."""
        text = line.upper()
        if 'VESSELS DUE AT OUTER ANCHORAGE' in text:
            return 'Outer Anchorage'
        if 'TANKER DUE' in text:
            return 'Tanker Due'
        if 'KUTUBDIA/MATARBARI ANCHORAGE' in text:
            return 'Kutubdia/Matarbari Anchorage'
        if 'VESSELS READY' in text:
            return 'Ready'
        if 'VESSELS NOT READY' in text:
            return 'Not Ready'
        if 'AWAITING EMPLOYEMENT' in text or 'AWAITING EMPLOYMENT' in text:
            return 'Awaiting Employment/Instruction'
        if 'VESSELS NOT ENTERING' in text:
            return 'Not Entering'
        return current_section

    def _clean_vessel_name(self, raw_name):
        """Remove CPA annotations from the vessel name while keeping the business name readable."""
        name = raw_name.strip().lstrip('*').strip()
        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r'\d{1,2}/\d{1,2}', '', name)
        return re.sub(r'\s+', ' ', name).strip()

    def _extract_imo(self, raw_name):
        imo_match = re.search(r'IMO\s*:?\s*([0-9 ]{6,9})', raw_name, re.IGNORECASE)
        if imo_match:
            return re.sub(r'\s+', '', imo_match.group(1))

        no_match = re.search(r'NO\.?\s*:?\s*([0-9 ]{4,})', raw_name, re.IGNORECASE)
        if no_match:
            return re.sub(r'\s+', '', no_match.group(1))

        return ''

    def _split_due_remainder(self, rest):
        tokens = rest.split()
        if len(tokens) < 3:
            return {
                'Last_Port': '',
                'Call_Flag': '',
                'Local_Agent': '',
                'Shipping_Line': '',
                'Cargo_Quantity': '',
                'Cargo_Type': '',
                'Loading_Port': '',
            }

        last_port, call_flag, local_agent = tokens[:3]
        remainder = tokens[3:]

        loading_port = remainder[-1] if remainder else ''
        cargo_type = remainder[-2] if len(remainder) >= 2 else ''
        cargo_quantity = remainder[-3] if len(remainder) >= 3 else ''
        shipping_line = ' '.join(remainder[:-3]) if len(remainder) > 3 else ''

        return {
            'Last_Port': last_port,
            'Call_Flag': call_flag,
            'Local_Agent': local_agent,
            'Shipping_Line': shipping_line,
            'Cargo_Quantity': cargo_quantity,
            'Cargo_Type': cargo_type,
            'Loading_Port': loading_port,
        }

    def _base_vessel(self, match, section, rest_fields):
        raw_name = match.group('name')
        return {
            'Vessel_Name': self._clean_vessel_name(raw_name),
            'IMO': self._extract_imo(raw_name),
            'Length': match.group('length'),
            'Draft': match.group('draft'),
            'Arrival_Date': match.group('arrival'),
            'GRT': match.group('grt'),
            'Last_Port': rest_fields.get('Last_Port', ''),
            'Call_Flag': rest_fields.get('Call_Flag', ''),
            'Local_Agent': rest_fields.get('Local_Agent', ''),
            'Shipping_Line': rest_fields.get('Shipping_Line', ''),
            'Cargo_Quantity': rest_fields.get('Cargo_Quantity', ''),
            'Cargo_Type': rest_fields.get('Cargo_Type', ''),
            'Loading_Port': rest_fields.get('Loading_Port', ''),
            'Section': section,
            'Update_Date': datetime.now().strftime('%d/%m/%Y')
        }

    def _parse_vessel_line(self, line, section='Outer Anchorage'):
        """Parse vessel information from text line"""
        try:
            if not self._is_vessel_line(line):
                return None

            due_pattern = re.compile(
                r'^\s*\d+\s+(?P<name>.+?)\s+'
                r'(?P<length>\d+\.\d+)\s+'
                r'(?P<draft>\d+(?:\.\d+)?)\s+'
                r'(?P<arrival>\d{2}/\d{2}/\d{2})\s+'
                r'(?P<grt>\d+|-)\s+'
                r'(?P<rest>.+)$'
            )
            due_match = due_pattern.match(line)
            if due_match:
                return self._base_vessel(
                    due_match,
                    section,
                    self._split_due_remainder(due_match.group('rest'))
                )

            anchorage_pattern = re.compile(
                r'^\s*\d+\s+(?P<name>.+?)\s+(?:-|\d{2}/\d{2})\s+'
                r'(?P<length>\d+\.\d+)\s+'
                r'(?P<cargo>.+?)\s+'
                r'(?P<grt>\d+|-)\s+'
                r'(?P<last_port>\S+)\s+'
                r'(?P<call_flag>\S+)\s+'
                r'(?P<local_agent>\S+)\s+'
                r'(?P<arrival>\d{2}/\d{2}/\d{2})\s+AT\s+\d{4}\s+'
                r'(?P<anchorage>[A-Z-])\s+'
                r'(?P<draft>\d+(?:\.\d+)?|-)\s*'
                r'(?P<quantity>.*)$'
            )
            anchorage_match = anchorage_pattern.match(line)
            if anchorage_match:
                return self._base_vessel(
                    anchorage_match,
                    section,
                    {
                        'Last_Port': anchorage_match.group('last_port'),
                        'Call_Flag': anchorage_match.group('call_flag'),
                        'Local_Agent': anchorage_match.group('local_agent'),
                        'Shipping_Line': '',
                        'Cargo_Quantity': anchorage_match.group('quantity').strip(),
                        'Cargo_Type': anchorage_match.group('cargo').strip(),
                        'Loading_Port': anchorage_match.group('anchorage'),
                    }
                )

            # "VESSELS AT OUTER ANCHORAGE" layout — waiting cargo ships whose row ends
            # "... DD/MM/YY AT HHMM  <draft> <grt>" with GRT last and no berth letter.
            # This block (AMOY FORTUNE, MELPOMENI, ORIENTE GLORIA, wheat/coal bulkers, ...)
            # matches neither pattern above and was being silently dropped.
            outer_wait_pattern = re.compile(
                r'^\s*\d+\s+(?P<name>.+?)\s*-\s+'
                r'(?P<length>\d+\.\d+)\s+'
                r'(?P<cargo>.+?)\s+'
                r'(?P<quantity>\d[\d/]*(?:\([^)]*\))?)\s+'
                r'(?P<last_port>\S+)\s+(?P<call_flag>\S+)\s+(?P<local_agent>\S+)\s+'
                r'(?P<arrival>\d{2}/\d{2}/\d{2})\s+AT\s+\d{4}\s+'
                r'(?P<draft>\d+(?:\.\d+)?|-)\s+'
                r'(?P<grt>\d+)(?:\([^)]*\))?\s*$'
            )
            outer_match = outer_wait_pattern.match(line)
            if outer_match:
                return self._base_vessel(
                    outer_match,
                    section,
                    {
                        'Last_Port': outer_match.group('last_port'),
                        'Call_Flag': outer_match.group('call_flag'),
                        'Local_Agent': outer_match.group('local_agent'),
                        'Shipping_Line': '',
                        'Cargo_Quantity': outer_match.group('quantity').strip(),
                        'Cargo_Type': outer_match.group('cargo').strip(),
                        'Loading_Port': '',
                    }
                )

            return None
        except Exception as e:
            logger.debug(f"Unable to parse vessel line: {line!r} ({str(e)})")
            return None

    def save_to_csv(self, vessels):
        """Save vessels to CSV file"""
        try:
            if not vessels:
                logger.warning("No vessels to save")
                return False

            logger.info("💾 Saving to CSV...")
            os.makedirs(self.project_dir, exist_ok=True)

            headers = ['SL.NO', 'Vessel_Name', 'IMO', 'Length', 'Draft', 'Arrival_Date', 'GRT',
                      'Last_Port', 'Call_Flag', 'Local_Agent', 'Shipping_Line', 'Cargo_Quantity',
                      'Cargo_Type', 'Loading_Port', 'Section', 'Update_Date']

            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

                for idx, vessel in enumerate(vessels, 1):
                    vessel['SL.NO'] = idx
                    writer.writerow(vessel)

            logger.info(f"✅ Saved {len(vessels)} vessels to CSV")
            return True

        except Exception as e:
            logger.error(f"CSV save failed: {str(e)}")
            return False

    def run(self):
        """Main execution"""
        logger.info("=" * 60)
        logger.info("🚢 PDF EXTRACTION TO CSV")
        logger.info("=" * 60)

        # Step 1: Get candidate PDFs from the listing (newest first)
        candidates = self.get_latest_pdf()
        if not candidates:
            logger.warning("No PDF found")
            return False

        # Step 2: Download the top candidates and pick the newest vessel
        # LINEUP (CPA also files berthing-position sheets under the same
        # doctype; those parse zero vessels and must be skipped).
        best = None
        for pdf_info in candidates[:8]:
            pdf_path = self.download_pdf(pdf_info)
            if not pdf_path:
                continue
            if not self._is_vessel_lineup(pdf_path):
                logger.info(f"⏭️  Skipping non-lineup doc: {pdf_info['filename'][:24]}...")
                continue
            dated = self._pdf_dated(pdf_path)
            logger.info(f"📅 {pdf_info['filename'][:24]}... -> DATED {dated:%d/%m/%Y if dated else 'n/a'}")
            if dated is None:
                continue
            if best is None or dated > best['dated']:
                best = {'pdf_info': pdf_info, 'dated': dated, 'pdf_path': pdf_path}

        if best is None:
            logger.error("❌ Could not determine the latest vessel PDF")
            return False

        pdf_info = best['pdf_info']
        pdf_path = best['pdf_path']
        logger.info(f"📄 Using newest vessel PDF: {pdf_info['filename']} (DATED {best['dated']:%d/%m/%Y})")

        # Step 3: Extract table
        vessels = self.extract_table_from_pdf(pdf_path)
        if not vessels:
            logger.error("No vessels extracted from PDF")
            return False

        # Step 4: Save to CSV
        if not self.save_to_csv(vessels):
            return False

        logger.info("=" * 60)
        logger.info("✅ PDF Extraction Complete!")
        logger.info("=" * 60)
        return True


if __name__ == "__main__":
    extractor = PDFExtractor()
    extractor.run()
