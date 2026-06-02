import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/data')))
from aa_scraper import extract_jsonld_blocks

class TestAAScraper(unittest.TestCase):
    def test_extract_valid_jsonld(self):
        html = '''
        <html>
            <head>
                <script type="application/ld+json">
                {"@type": "Dataset", "name": "Test Dataset", "data": [{"foo": "bar"}]}
                </script>
                <script type="application/ld+json">
                {"@type": "Dataset", "name": "Another Dataset", "data": []}
                </script>
            </head>
        </html>
        '''
        blocks = extract_jsonld_blocks(html)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["name"], "Test Dataset")

    def test_extract_invalid_jsonld(self):
        html = '''
        <script type="application/ld+json">
        {"@type": "Dataset", "name": "Test Dataset", "data": 
        </script>
        '''
        blocks = extract_jsonld_blocks(html)
        self.assertEqual(len(blocks), 0)

    def test_extract_ignores_non_dataset(self):
        html = '''
        <script type="application/ld+json">
        {"@type": "Person", "name": "John Doe"}
        </script>
        <script type="application/ld+json">
        {"@type": "Dataset", "name": "Good Dataset"}
        </script>
        '''
        blocks = extract_jsonld_blocks(html)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["name"], "Good Dataset")

if __name__ == "__main__":
    unittest.main()
