"""Tests for illustrative exercise media: Wikimedia Commons images and YouTube video proposals."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from associate_exercise_media import (
    clean_exercise_name_for_search,
    strip_html,
    parse_imageinfo,
    parse_youtube_search_results,
    load_media_index,
    save_media_index,
    associate_exercise_media,
    EXERCISE_DISCLAIMER,
)


class ExerciseMediaTests(unittest.TestCase):
    def test_clean_exercise_name_for_search(self):
        """Test name cleanup removes hyphens, underscores, brackets, and extra spaces."""
        self.assertEqual(clean_exercise_name_for_search("dumbbell-deadlift"), "dumbbell deadlift")
        self.assertEqual(clean_exercise_name_for_search("bodyweight_squat"), "bodyweight squat")
        self.assertEqual(clean_exercise_name_for_search("push-up (beginner variation)"), "push up")
        self.assertEqual(clean_exercise_name_for_search("inverted-row [gym version]"), "inverted row")
        self.assertEqual(clean_exercise_name_for_search(""), "")

    def test_strip_html_and_url_normalization(self):
        """Test extraction of clean text and author URL from MediaWiki HTML."""
        text1 = '<a href="https://commons.wikimedia.org/wiki/User:Athlete">Coach Alex</a>'
        name1, url1 = strip_html(text1)
        self.assertEqual(name1, "Coach Alex")
        self.assertEqual(url1, "https://commons.wikimedia.org/wiki/User:Athlete")

        text2 = '<a href="//commons.wikimedia.org/w/index.php?title=User:Trainer&amp;action=edit">Trainer Bob</a>'
        name2, url2 = strip_html(text2)
        self.assertEqual(name2, "Trainer Bob")
        self.assertEqual(url2, "https://commons.wikimedia.org/w/index.php?title=User:Trainer&action=edit")

        name3, url3 = strip_html("Plain Trainer Name")
        self.assertEqual(name3, "Plain Trainer Name")
        self.assertIsNone(url3)

    def test_parse_imageinfo_success(self):
        """Test parsing valid MediaWiki imageinfo record extracts license, author, and disclaimer."""
        mock_page = {
            'pageid': 99999,
            'title': 'File:Dumbbell Bench Press.jpg',
            'imageinfo': [
                {
                    'mime': 'image/jpeg',
                    'url': 'https://upload.wikimedia.org/example-bench.jpg',
                    'thumburl': 'https://thumb.wikimedia.org/example-bench-thumb.jpg',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Dumbbell_Bench_Press.jpg',
                    'extmetadata': {
                        'Artist': {'value': '<a href="https://example.com/user">GymPhotographer</a>'},
                        'LicenseShortName': {'value': 'CC BY-SA 4.0'},
                        'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by-sa/4.0/'},
                        'Credit': {'value': 'Gym Photography'},
                    },
                }
            ],
        }
        res = parse_imageinfo(mock_page, "Dumbbell Bench Press", "dumbbell-bench-press", "Dumbbell Bench Press")
        self.assertIsNotNone(res)
        self.assertEqual(res['exercise_id'], "dumbbell-bench-press")
        self.assertEqual(res['author'], "GymPhotographer")
        self.assertEqual(res['author_url'], "https://example.com/user")
        self.assertEqual(res['license'], "CC BY-SA 4.0")
        self.assertEqual(res['license_url'], "https://creativecommons.org/licenses/by-sa/4.0/")
        self.assertEqual(res['source'], "Wikimedia Commons")
        self.assertTrue(res['illustrative'])
        self.assertEqual(res['disclaimer'], EXERCISE_DISCLAIMER)

    def test_parse_imageinfo_filters_non_photos_and_diagrams(self):
        """Test filtering out SVG, audio, icons, maps, and diagrams."""
        svg_page = {
            'title': 'File:Exercise_icon.svg',
            'imageinfo': [{'mime': 'image/svg+xml', 'url': 'https://example.com/icon.svg'}],
        }
        self.assertIsNone(parse_imageinfo(svg_page, "Plank", "plank", "Plank"))

        diagram_page = {
            'title': 'File:Muscle anatomy diagram.jpg',
            'imageinfo': [{'mime': 'image/jpeg', 'url': 'https://example.com/diagram.jpg'}],
        }
        self.assertIsNone(parse_imageinfo(diagram_page, "Plank", "plank", "Plank"))

    def test_parse_youtube_search_results(self):
        """Test parsing of simulated ytInitialData structure for YouTube search results."""
        mock_initial_data = {
            'contents': {
                'twoColumnSearchResultsRenderer': {
                    'primaryContents': {
                        'sectionListRenderer': {
                            'contents': [
                                {
                                    'itemSectionRenderer': {
                                        'contents': [
                                            {
                                                'videoRenderer': {
                                                    'videoId': 'abc123xyz',
                                                    'title': {'runs': [{'text': 'Perfect Push Up Form Tutorial'}]},
                                                    'ownerText': {'runs': [{'text': 'Fitness Channel'}]},
                                                    'lengthText': {'simpleText': '5:24'},
                                                    'thumbnail': {
                                                        'thumbnails': [
                                                            {'url': 'https://i.ytimg.com/vi/abc123xyz/default.jpg'},
                                                            {'url': 'https://i.ytimg.com/vi/abc123xyz/hqdefault.jpg'},
                                                        ]
                                                    },
                                                }
                                            },
                                            {
                                                'videoRenderer': {
                                                    'videoId': 'def456uvw',
                                                    'title': {'simpleText': 'Top 5 Pushup Mistakes'},
                                                    'ownerText': {'runs': [{'text': 'Calisthenics Pro'}]},
                                                    'lengthText': {'simpleText': '3:12'},
                                                    'thumbnail': {
                                                        'thumbnails': [
                                                            {'url': 'https://i.ytimg.com/vi/def456uvw/hqdefault.jpg'}
                                                        ]
                                                    },
                                                }
                                            },
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        mock_html = f"<html><script>var ytInitialData = {json.dumps(mock_initial_data)};</script></html>"
        results = parse_youtube_search_results(mock_html, max_results=3)

        self.assertEqual(len(results), 2)
        v1 = results[0]
        self.assertEqual(v1['video_id'], 'abc123xyz')
        self.assertEqual(v1['title'], 'Perfect Push Up Form Tutorial')
        self.assertEqual(v1['channel'], 'Fitness Channel')
        self.assertEqual(v1['duration'], '5:24')
        self.assertEqual(v1['url'], 'https://www.youtube.com/watch?v=abc123xyz')
        self.assertEqual(v1['thumbnail_url'], 'https://i.ytimg.com/vi/abc123xyz/hqdefault.jpg')

        v2 = results[1]
        self.assertEqual(v2['video_id'], 'def456uvw')
        self.assertEqual(v2['title'], 'Top 5 Pushup Mistakes')
        self.assertEqual(v2['channel'], 'Calisthenics Pro')

    def test_offline_mode_does_not_query_network(self):
        """Running without --online processes strictly offline and updates nothing."""
        mock_output = Path('/tmp/test_offline_exercise_media.json')
        if mock_output.exists():
            mock_output.unlink()

        res = associate_exercise_media(
            source_path=ROOT / 'dataset/repdb/raw/exercises.json',
            media_path=mock_output,
            online=False,
            sample=3,
        )
        self.assertEqual(res['updated'], 0)
        self.assertEqual(res['total_examined'], 3)
        self.assertEqual(res['total_in_index'], 0)

    def test_exercise_media_index_structure(self):
        """Test that the live config/exercise-media.json has valid structure, disclaimer, and media."""
        media_path = ROOT / 'config/exercise-media.json'
        self.assertTrue(media_path.exists(), "config/exercise-media.json must exist")

        data = load_media_index(media_path)
        self.assertIn('version', data)
        self.assertIn('exercises', data)

        exercises = data['exercises']
        self.assertGreater(len(exercises), 0, "Expected at least one exercise in config/exercise-media.json")

        for ex_id, item in exercises.items():
            self.assertEqual(item['exercise_id'], ex_id)
            self.assertIn('disclaimer', item)
            self.assertEqual(item['disclaimer'], EXERCISE_DISCLAIMER)

            if item.get('illustrative_image'):
                img = item['illustrative_image']
                self.assertTrue(img['illustrative'])
                self.assertIn('image_url', img)
                self.assertIn('source', img)
                self.assertIn('license', img)
                self.assertIn('author', img)
                self.assertEqual(img['disclaimer'], EXERCISE_DISCLAIMER)

            if item.get('youtube_videos'):
                for vid in item['youtube_videos']:
                    self.assertIn('video_id', vid)
                    self.assertIn('title', vid)
                    self.assertIn('channel', vid)
                    self.assertIn('url', vid)
                    self.assertTrue(vid['url'].startswith('https://www.youtube.com/watch?v='))


if __name__ == '__main__':
    unittest.main()
