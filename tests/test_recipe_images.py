"""Tests for illustrative recipe images: metadata parsing, licensing, and API integration."""

import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'web'))

from associate_recipe_images import (
    clean_title_for_search,
    strip_html,
    parse_imageinfo,
    load_images_index,
    save_images_index,
    associate_images,
    DISCLAIMER
)


class RecipeImagesTests(unittest.TestCase):
    def test_clean_title_for_search(self):
        """Test search query cleanup removes bracketed notes, symbols, and extra spaces."""
        self.assertEqual(clean_title_for_search("Pasta al pomodoro · ricetta dimostrativa"), "Pasta al pomodoro ricetta dimostrativa")
        self.assertEqual(clean_title_for_search("Spaghetti carbonara (classic Italian)"), "Spaghetti carbonara")
        self.assertEqual(clean_title_for_search("Dish [with notes] - special"), "Dish special")

    def test_strip_html_and_url_normalization(self):
        """Test extraction of clean text and normalized author URL from MediaWiki HTML."""
        # Standard link
        text1 = '<a href="https://commons.wikimedia.org/wiki/User:Chef">Chef Mario</a>'
        name1, url1 = strip_html(text1)
        self.assertEqual(name1, "Chef Mario")
        self.assertEqual(url1, "https://commons.wikimedia.org/wiki/User:Chef")

        # Protocol-relative URL with entities
        text2 = '<a href="//commons.wikimedia.org/w/index.php?title=User:Test&amp;action=edit">Test Author</a>'
        name2, url2 = strip_html(text2)
        self.assertEqual(name2, "Test Author")
        self.assertEqual(url2, "https://commons.wikimedia.org/w/index.php?title=User:Test&action=edit")

        # Plain text without HTML
        name3, url3 = strip_html("Plain Name")
        self.assertEqual(name3, "Plain Name")
        self.assertIsNone(url3)

    def test_parse_imageinfo_success(self):
        """Test parsing valid MediaWiki imageinfo record extracts license, author, and disclaimer."""
        mock_page = {
            'pageid': 12345,
            'title': 'File:Delicious Carbonara.jpg',
            'imageinfo': [
                {
                    'mime': 'image/jpeg',
                    'url': 'https://upload.wikimedia.org/example.jpg',
                    'thumburl': 'https://thumb.wikimedia.org/example-thumb.jpg',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Delicious_Carbonara.jpg',
                    'extmetadata': {
                        'Artist': {'value': '<a href="https://example.com/user">Foodie</a>'},
                        'LicenseShortName': {'value': 'CC BY-SA 4.0'},
                        'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by-sa/4.0/'},
                        'Credit': {'value': 'Foodie Photography'}
                    }
                }
            ]
        }
        res = parse_imageinfo(mock_page, "Spaghetti carbonara", "unitools:carbonara", "Spaghetti carbonara")
        self.assertIsNotNone(res)
        self.assertEqual(res['recipe_id'], "unitools:carbonara")
        self.assertEqual(res['author'], "Foodie")
        self.assertEqual(res['author_url'], "https://example.com/user")
        self.assertEqual(res['license'], "CC BY-SA 4.0")
        self.assertEqual(res['license_url'], "https://creativecommons.org/licenses/by-sa/4.0/")
        self.assertEqual(res['source'], "Wikimedia Commons")
        self.assertTrue(res['illustrative'])
        self.assertEqual(res['disclaimer'], DISCLAIMER)

    def test_parse_imageinfo_filters_non_photos_and_icons(self):
        """Test filtering out SVG, audio, icons, maps, and logos."""
        # Non-photo mime type (SVG)
        svg_page = {
            'title': 'File:Cooking_icon.svg',
            'imageinfo': [{'mime': 'image/svg+xml', 'url': 'https://example.com/icon.svg'}]
        }
        self.assertIsNone(parse_imageinfo(svg_page, "Dish", "rec:1", "Dish"))

        # Icon in title
        icon_page = {
            'title': 'File:Recipe icon food.jpg',
            'imageinfo': [{'mime': 'image/jpeg', 'url': 'https://example.com/icon.jpg'}]
        }
        self.assertIsNone(parse_imageinfo(icon_page, "Dish", "rec:1", "Dish"))

    def test_offline_mode_does_not_query_network(self):
        """Running without --online processes strictly offline and updates nothing."""
        mock_output = Path('/tmp/test_offline_images.json')
        if mock_output.exists():
            mock_output.unlink()

        res = associate_images(
            recipes_db_path=ROOT / 'dataset/recipes/catalog.sqlite',
            images_path=mock_output,
            online=False,
            sample=3
        )
        self.assertEqual(res['updated'], 0)
        self.assertEqual(res['total_examined'], 3)
        self.assertEqual(res['total_in_index'], 0)

    def test_web_api_attaches_illustrative_images(self):
        """Test FastAPI /api/recipes includes illustrative_image metadata when available."""
        import importlib.util
        import os
        import tempfile
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['DIET_WEB_DB'] = str(Path(tmpdir) / 'test.sqlite')
            spec = importlib.util.spec_from_file_location('test_images_web', ROOT / 'web/app.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            del os.environ['DIET_WEB_DB']

            module.initialize()
            client = TestClient(module.app)

            # Register and log in
            client.post('/api/register', json={'username': 'testuser', 'password': 'testpassword123'})
            login_res = client.post('/api/login', json={'username': 'testuser', 'password': 'testpassword123'})
            self.assertEqual(login_res.status_code, 200)

            # Query recipes
            resp = client.get('/api/recipes?q=carbonara')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertGreater(data['total'], 0)

            # Carbonara is present in config/recipe-images.json
            carb_recipe = next((r for r in data['recipes'] if r['id'] == 'unitools:spaghetti-carbonara'), None)
            self.assertIsNotNone(carb_recipe)
            self.assertIn('illustrative_image', carb_recipe)
            img = carb_recipe['illustrative_image']
            self.assertTrue(img['illustrative'])
            self.assertIn('license', img)
            self.assertIn('author', img)
            self.assertIn('source_page', img)
            self.assertEqual(img['disclaimer'], DISCLAIMER)


if __name__ == '__main__':
    unittest.main()
