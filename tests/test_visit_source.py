import unittest

from app import (
    PROJECT_CATEGORY_INTERACTIVE,
    PROJECT_CATEGORY_MUSICAL,
    build_projects_overview,
    format_visit_origin_label,
    infer_project_category,
    infer_source,
    normalize_project_category_key,
    parse_project_changelog_entries,
    parse_project_changelog_text,
    resolve_project_category_directory,
)


class VisitSourceInferenceTests(unittest.TestCase):
    def test_internal_referrer_wins_over_in_app_user_agent(self):
        source = infer_source(
            current_host="provingchill.sytes.net",
            explicit_source="",
            referrer_domain="provingchill.sytes.net",
            user_agent="Mozilla/5.0 Instagram 425.0",
            requested_with="com.instagram.android",
            sec_fetch_site="same-origin",
        )

        self.assertEqual(source, "internal")

    def test_cross_site_navigation_without_referrer_is_generic_link(self):
        source = infer_source(
            current_host="provingchill.sytes.net",
            explicit_source="",
            referrer_domain="",
            user_agent="Mozilla/5.0 AppleWebKit/537.36 Chrome/147.0.0.0 Mobile Safari/537.36",
            requested_with="",
            sec_fetch_site="cross-site",
        )

        self.assertEqual(source, "link")

    def test_requested_with_detects_whatsapp(self):
        source = infer_source(
            current_host="provingchill.sytes.net",
            explicit_source="",
            referrer_domain="",
            user_agent="Mozilla/5.0 AppleWebKit/537.36 Chrome/147.0.0.0 Mobile Safari/537.36",
            requested_with="com.whatsapp",
            sec_fetch_site="none",
        )

        self.assertEqual(source, "whatsapp")

    def test_referrer_domain_detects_telegram(self):
        source = infer_source(
            current_host="provingchill.sytes.net",
            explicit_source="",
            referrer_domain="t.me",
            user_agent="Mozilla/5.0",
            requested_with="",
            sec_fetch_site="cross-site",
        )

        self.assertEqual(source, "telegram")

    def test_platform_label_prefers_detected_source_over_referrer_domain(self):
        label = format_visit_origin_label("instagram", "l.instagram.com")

        self.assertEqual(label, "Instagram")


class ProjectCategoryDirectoryTests(unittest.TestCase):
    def test_normalize_category_key_handles_spaces_and_accents(self):
        normalized = normalize_project_category_key("Páginas Musicales")

        self.assertEqual(normalized, "paginas-musicales")

    def test_resolve_interactive_category_from_folder_name(self):
        category = resolve_project_category_directory("paginas interactivas")

        self.assertEqual(category, PROJECT_CATEGORY_INTERACTIVE)

    def test_direct_root_projects_stay_musical_by_default(self):
        category = infer_project_category()

        self.assertEqual(category, PROJECT_CATEGORY_MUSICAL)


class ProjectMetadataTests(unittest.TestCase):
    def test_parse_changelog_entries_from_json_shape(self):
        entries = parse_project_changelog_entries(
            [
                {
                    "version": "v1.2.0",
                    "date": "2026-05-13",
                    "changes": ["Consola Linux publica", "Likes por proyecto"],
                }
            ]
        )

        self.assertEqual(entries[0]["version"], "v1.2.0")
        self.assertEqual(entries[0]["date"], "2026-05-13")
        self.assertEqual(entries[0]["notes"], ["Consola Linux publica", "Likes por proyecto"])

    def test_parse_changelog_entries_from_markdown_headings(self):
        entries = parse_project_changelog_text(
            """
            ## v1.1.0
            - Nuevo monitor publico
            - Changelog por proyecto
            """
        )

        self.assertEqual(entries[0]["version"], "v1.1.0")
        self.assertEqual(entries[0]["notes"], ["Nuevo monitor publico", "Changelog por proyecto"])

    def test_build_projects_overview_uses_project_views_and_likes(self):
        overview = build_projects_overview(
            [
                {"title": "A", "visit_count": 10, "like_count": 3, "updated_at": "2026-05-10"},
                {"title": "B", "visit_count": 4, "like_count": 8, "updated_at": "2026-05-11"},
            ]
        )

        self.assertEqual(overview["project_views"], 14)
        self.assertEqual(overview["total_likes"], 11)
        self.assertEqual(overview["featured_pages"][0]["title"], "B")


if __name__ == "__main__":
    unittest.main()
