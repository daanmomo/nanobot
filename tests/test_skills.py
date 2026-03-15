"""Tests for skills loader and built-in skills."""

from pathlib import Path

import pytest

from nanobot.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader


class TestSkillsLoader:
    """Tests for the SkillsLoader class."""

    @pytest.fixture
    def temp_workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace for testing."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return workspace

    @pytest.fixture
    def loader(self, temp_workspace: Path) -> SkillsLoader:
        """Create a SkillsLoader with temporary workspace."""
        return SkillsLoader(temp_workspace, builtin_skills_dir=BUILTIN_SKILLS_DIR)

    def test_list_builtin_skills(self, loader: SkillsLoader) -> None:
        """Test listing built-in skills."""
        skills = loader.list_skills(filter_unavailable=False)
        skill_names = [s["name"] for s in skills]

        # Check core skills exist
        assert "cron" in skill_names
        assert "summarize" in skill_names

    def test_load_cron_skill(self, loader: SkillsLoader) -> None:
        """Test loading the cron skill."""
        content = loader.load_skill("cron")
        assert content is not None
        assert "cron" in content.lower()

    def test_load_nonexistent_skill(self, loader: SkillsLoader) -> None:
        """Test loading a skill that doesn't exist."""
        content = loader.load_skill("nonexistent-skill-xyz")
        assert content is None

    def test_workspace_skill_priority(self, temp_workspace: Path) -> None:
        """Test that workspace skills override built-in skills."""
        # Create a workspace skill that overrides a built-in
        skill_dir = temp_workspace / "skills" / "cron"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Custom Cron Skill\n\nOverridden!")

        loader = SkillsLoader(temp_workspace, builtin_skills_dir=BUILTIN_SKILLS_DIR)
        content = loader.load_skill("cron")
        assert "Overridden!" in content

    def test_get_skill_metadata(self, loader: SkillsLoader) -> None:
        """Test extracting metadata from skill frontmatter."""
        # The cron skill should have metadata
        meta = loader.get_skill_metadata("cron")
        if meta:
            assert "name" in meta or "description" in meta

    def test_build_skills_summary(self, loader: SkillsLoader) -> None:
        """Test building skills summary XML."""
        summary = loader.build_skills_summary()
        assert "<skills>" in summary
        assert "</skills>" in summary
        assert "<skill" in summary
        assert "<name>" in summary

    def test_custom_workspace_skill(self, temp_workspace: Path) -> None:
        """Test creating and loading a custom skill."""
        # Create custom skill
        skill_dir = temp_workspace / "skills" / "my-custom-skill"
        skill_dir.mkdir(parents=True)
        skill_content = """---
name: my-custom-skill
description: A custom test skill
---

# My Custom Skill

This is a test skill.
"""
        (skill_dir / "SKILL.md").write_text(skill_content)

        loader = SkillsLoader(temp_workspace, builtin_skills_dir=BUILTIN_SKILLS_DIR)

        # Should appear in list
        skills = loader.list_skills(filter_unavailable=False)
        skill_names = [s["name"] for s in skills]
        assert "my-custom-skill" in skill_names

        # Should be loadable
        content = loader.load_skill("my-custom-skill")
        assert content is not None
        assert "My Custom Skill" in content

    def test_strip_frontmatter(self, loader: SkillsLoader) -> None:
        """Test that frontmatter is stripped when loading for context."""
        content = loader.load_skills_for_context(["cron"])
        # Should not contain frontmatter markers
        if content:
            assert not content.startswith("---")


class TestResearchSkill:
    """Tests for the research skill."""

    @pytest.fixture
    def loader(self, tmp_path: Path) -> SkillsLoader:
        return SkillsLoader(tmp_path, builtin_skills_dir=BUILTIN_SKILLS_DIR)

    def test_research_skill_exists(self, loader: SkillsLoader) -> None:
        """Test that the research skill exists."""
        skills = loader.list_skills(filter_unavailable=False)
        skill_names = [s["name"] for s in skills]
        assert "research" in skill_names

    def test_research_skill_content(self, loader: SkillsLoader) -> None:
        """Test research skill content has expected sections."""
        content = loader.load_skill("research")
        assert content is not None
        # Check for key sections
        assert "研究" in content or "research" in content.lower()
        assert "spawn" in content.lower() or "子" in content

    def test_research_skill_metadata(self, loader: SkillsLoader) -> None:
        """Test research skill metadata (may be None if no frontmatter)."""
        meta = loader.get_skill_metadata("research")
        # Metadata may be None if skill doesn't have frontmatter
        # Just verify the method doesn't crash
        if meta is not None:
            assert isinstance(meta, dict)


class TestStockSkill:
    """Tests for the stock skill."""

    @pytest.fixture
    def loader(self, tmp_path: Path) -> SkillsLoader:
        return SkillsLoader(tmp_path, builtin_skills_dir=BUILTIN_SKILLS_DIR)

    def test_stock_skill_exists(self, loader: SkillsLoader) -> None:
        """Test that the stock skill exists."""
        skills = loader.list_skills(filter_unavailable=False)
        skill_names = [s["name"] for s in skills]
        assert "stock" in skill_names

    def test_stock_skill_content(self, loader: SkillsLoader) -> None:
        """Test stock skill content has expected sections."""
        content = loader.load_skill("stock")
        assert content is not None
        # Check for key sections - stock analysis skill
        assert "stock" in content.lower() or "股票" in content
        # Should mention tools
        assert "stock_" in content or "行情" in content

    def test_stock_skill_tools_documented(self, loader: SkillsLoader) -> None:
        """Test that stock tools are documented in the skill."""
        content = loader.load_skill("stock")
        assert content is not None
        # Key tools should be mentioned
        expected_tools = [
            "stock_get_watchlist",
            "stock_add",
            "stock_realtime_quote",
            "stock_history",
            "stock_indicators",
        ]
        for tool in expected_tools:
            assert tool in content, f"Tool {tool} not documented in stock skill"


class TestBrowserSkill:
    """Tests for the browser skill."""

    @pytest.fixture
    def loader(self, tmp_path: Path) -> SkillsLoader:
        return SkillsLoader(tmp_path, builtin_skills_dir=BUILTIN_SKILLS_DIR)

    def test_browser_skill_exists(self, loader: SkillsLoader) -> None:
        """Test that the browser skill exists."""
        skills = loader.list_skills(filter_unavailable=False)
        skill_names = [s["name"] for s in skills]
        assert "browser" in skill_names

    def test_browser_skill_content(self, loader: SkillsLoader) -> None:
        """Test browser skill content has expected sections."""
        content = loader.load_skill("browser")
        assert content is not None
        # Check for key sections
        assert "playwright" in content.lower()
        assert "browser" in content.lower()

    def test_browser_skill_has_setup_instructions(self, loader: SkillsLoader) -> None:
        """Test browser skill has setup instructions."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should have installation commands
        assert "pip install playwright" in content
        assert "playwright install" in content

    def test_browser_skill_has_examples(self, loader: SkillsLoader) -> None:
        """Test browser skill has code examples."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should have Python examples
        assert "sync_playwright" in content
        assert "page.goto" in content
        assert "screenshot" in content.lower()

    def test_browser_skill_metadata(self, loader: SkillsLoader) -> None:
        """Test browser skill has proper metadata."""
        meta = loader.get_skill_metadata("browser")
        assert meta is not None
        assert meta.get("name") == "browser"
        assert "description" in meta
        # Check metadata JSON contains requirements
        assert "metadata" in meta
        assert "playwright" in meta["metadata"]

    def test_browser_skill_documents_common_operations(self, loader: SkillsLoader) -> None:
        """Test browser skill documents common operations."""
        content = loader.load_skill("browser")
        assert content is not None
        # Key operations should be documented
        operations = [
            "goto",
            "screenshot",
            "fill",
            "click",
            "wait_for",
            "locator",
        ]
        for op in operations:
            assert op in content, f"Operation {op} not documented in browser skill"

    def test_browser_skill_has_cli_usage(self, loader: SkillsLoader) -> None:
        """Test browser skill documents CLI usage."""
        content = loader.load_skill("browser")
        assert content is not None
        # CLI commands should be documented
        assert "playwright open" in content or "playwright codegen" in content

    def test_browser_skill_requires_playwright(self, loader: SkillsLoader) -> None:
        """Test browser skill requires playwright binary."""
        meta = loader.get_skill_metadata("browser")
        assert meta is not None
        metadata_json = meta.get("metadata", "")
        # The metadata should specify playwright as a required binary
        assert "playwright" in metadata_json
        assert "requires" in metadata_json

    def test_browser_skill_has_download_capability(self, loader: SkillsLoader) -> None:
        """Test browser skill documents file download capability."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should document download functionality
        assert "download" in content.lower()
        assert "expect_download" in content
        assert "save_as" in content

    def test_browser_skill_specifies_download_directory(self, loader: SkillsLoader) -> None:
        """Test browser skill specifies the download directory."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should mention the tmp directory
        assert "tmp" in content
        assert "DOWNLOAD_DIR" in content

    def test_browser_skill_has_file_analysis_examples(self, loader: SkillsLoader) -> None:
        """Test browser skill has file analysis examples."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should have examples for analyzing different file types
        assert "csv" in content.lower()
        assert "json" in content.lower()
        assert "pdf" in content.lower()

    def test_browser_skill_has_paper_download_section(self, loader: SkillsLoader) -> None:
        """Test browser skill has paper download and analysis section."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should have paper download section
        assert "Paper Download" in content or "paper" in content.lower()
        assert "arxiv" in content.lower()

    def test_browser_skill_has_doubao_example(self, loader: SkillsLoader) -> None:
        """Test browser skill has example for 豆包 paper search."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should have Chinese example for Doubao paper
        assert "豆包" in content or "Doubao" in content or "ByteDance" in content

    def test_browser_skill_has_summary_generation(self, loader: SkillsLoader) -> None:
        """Test browser skill documents summary report generation."""
        content = loader.load_skill("browser")
        assert content is not None
        # Should have summary/report generation
        assert "summary" in content.lower() or "总结" in content
        assert "generate" in content.lower() or "生成" in content


class TestBrowserSkillScripts:
    """Tests for browser skill scripts."""

    def test_download_paper_script_exists(self) -> None:
        """Test that download_paper.py script exists."""
        script_path = BUILTIN_SKILLS_DIR / "browser" / "scripts" / "download_paper.py"
        assert script_path.exists(), "download_paper.py script should exist"

    def test_download_paper_script_has_search_function(self) -> None:
        """Test download_paper.py has search_arxiv function."""
        script_path = BUILTIN_SKILLS_DIR / "browser" / "scripts" / "download_paper.py"
        content = script_path.read_text()
        assert "def search_arxiv" in content
        assert "def download_pdf" in content
        assert "def extract_pdf_text" in content
        assert "def generate_summary" in content

    def test_download_paper_script_uses_correct_directory(self) -> None:
        """Test download_paper.py uses nanobot/tmp directory."""
        script_path = BUILTIN_SKILLS_DIR / "browser" / "scripts" / "download_paper.py"
        content = script_path.read_text()
        assert "tmp" in content
        assert "DOWNLOAD_DIR" in content


class TestSkillRequirements:
    """Tests for skill requirements checking."""

    @pytest.fixture
    def temp_workspace(self, tmp_path: Path) -> Path:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return workspace

    def test_skill_with_bin_requirement(self, temp_workspace: Path) -> None:
        """Test skill with binary requirement."""
        # Create skill with requirement
        skill_dir = temp_workspace / "skills" / "needs-bin"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: needs-bin
description: Needs a binary
metadata: '{"nanobot": {"requires": {"bins": ["nonexistent-binary-xyz"]}}}'
---

# Needs Binary
""")

        loader = SkillsLoader(temp_workspace, builtin_skills_dir=None)

        # Should be in unfiltered list
        all_skills = loader.list_skills(filter_unavailable=False)
        assert any(s["name"] == "needs-bin" for s in all_skills)

        # Should NOT be in filtered list (requirement not met)
        available = loader.list_skills(filter_unavailable=True)
        assert not any(s["name"] == "needs-bin" for s in available)

    def test_skill_without_requirements(self, temp_workspace: Path) -> None:
        """Test skill without requirements is always available."""
        skill_dir = temp_workspace / "skills" / "no-reqs"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""---
name: no-reqs
description: No requirements
---

# No Requirements
""")

        loader = SkillsLoader(temp_workspace, builtin_skills_dir=None)

        # Should be in both lists
        all_skills = loader.list_skills(filter_unavailable=False)
        available = loader.list_skills(filter_unavailable=True)

        assert any(s["name"] == "no-reqs" for s in all_skills)
        assert any(s["name"] == "no-reqs" for s in available)
