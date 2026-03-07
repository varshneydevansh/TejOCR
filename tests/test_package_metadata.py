# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import unittest
import xml.etree.ElementTree as ET


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
DESCRIPTION_XML = os.path.join(PROJECT_ROOT, "description.xml")
MANIFEST_XML = os.path.join(PROJECT_ROOT, "META-INF", "manifest.xml")


class TestPackageMetadata(unittest.TestCase):
    def test_simple_license_default_id_has_matching_license_text_when_present(self):
        tree = ET.parse(DESCRIPTION_XML)
        root = tree.getroot()
        ns = {
            "desc": "http://openoffice.org/extensions/description/2006",
            "xlink": "http://www.w3.org/1999/xlink",
        }

        for simple_license in root.findall(".//desc:simple-license", ns):
            default_license_id = simple_license.get("default-license-id")
            license_texts = simple_license.findall("desc:license-text", ns)

            if not default_license_id:
                continue

            license_ids = [item.get("license-id") for item in license_texts if item.get("license-id")]
            self.assertIn(
                default_license_id,
                license_ids,
                "description.xml has default-license-id but no matching license-text license-id",
            )

    def test_license_text_href_exists_and_is_listed_in_manifest(self):
        desc_tree = ET.parse(DESCRIPTION_XML)
        desc_root = desc_tree.getroot()
        ns = {
            "desc": "http://openoffice.org/extensions/description/2006",
            "xlink": "http://www.w3.org/1999/xlink",
            "manifest": "http://openoffice.org/2001/manifest",
        }

        manifest_tree = ET.parse(MANIFEST_XML)
        manifest_root = manifest_tree.getroot()
        manifest_paths = {
            entry.get("{http://openoffice.org/2001/manifest}full-path")
            for entry in manifest_root.findall("manifest:file-entry", ns)
        }

        for license_text in desc_root.findall(".//desc:license-text", ns):
            href = license_text.get("{http://www.w3.org/1999/xlink}href")
            self.assertTrue(href, "license-text is missing xlink:href")
            self.assertTrue(
                os.path.exists(os.path.join(PROJECT_ROOT, href)),
                "description.xml references missing license resource: {href}".format(href=href),
            )
            self.assertIn(
                href,
                manifest_paths,
                "manifest.xml is missing a file-entry for the license resource: {href}".format(href=href),
            )


if __name__ == "__main__":
    unittest.main()
