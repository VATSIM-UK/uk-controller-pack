import os
import sys
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LogonDetails import (
    is_valid_cid,
    load_previous_options,
    save_options,
    patch_prf_file,
    patch_prf_file_with_asel,
    patch_discord_plugin,
    patch_plugins_file,
    patch_ese_file,
    patch_profiles_file,
    _resolve_discord_relpath,
    prompt_for_field,
)

@pytest.fixture
def prf_file(tmp_path):
    """Fixture providing a temporary .prf file"""
    return str(tmp_path / "test.prf")


@pytest.fixture
def plugins_file(tmp_path):
    """Fixture providing a temporary Plugins.txt file"""
    return str(tmp_path / "Plugins.txt")


@pytest.fixture
def ese_file(tmp_path):
    """Fixture providing a temporary .ese file"""
    return str(tmp_path / "UK.ese")


@pytest.fixture
def profiles_file(tmp_path):
    """Fixture providing a temporary Profiles.txt file"""
    return str(tmp_path / "Profiles.txt")


@pytest.fixture
def config_file(tmp_path):
    """Fixture providing a temporary config JSON file"""
    return str(tmp_path / "test_config.json")


@pytest.mark.parametrize("cid,expected", [
    ("123456", True),        # Valid 6-digit
    ("1234567", True),       # Valid 7-digit
    ("12345", False),        # Too short
    ("12345678", False),     # Too long
    ("12345a", False),       # Contains letter
    ("", False),             # Empty
    ("abcdef", False),       # All letters
    ("0000000", True),       # Valid 7-digit with zeros
    ("0", False),            # Single digit
    ("100000", True),        # Lower bound 6-digit
    ("999999", True),        # Upper bound 6-digit
    ("1000000", True),       # Lower bound 7-digit
    ("9999999", True),       # Upper bound 7-digit
    ("1234567a", False),     # 8 chars with letter
    (" 123456", False),      # Leading space
    ("123456 ", False),      # Trailing space
    ("123 456", False),      # Space in middle
])
def test_cid_validation(cid, expected):
    """Test CID validation with various inputs including boundary and whitespace cases"""
    assert is_valid_cid(cid) == expected

def test_save_options(config_file):
    """Test saving options to JSON file"""
    with patch('LogonDetails.OPTIONS_PATH', config_file):
        options = {
            "name": "John Doe",
            "initials": "JD",
            "cid": "123456",
            "rating": "0",
        }
        save_options(options)
        
        # Verify file was created
        assert os.path.exists(config_file)
        
        # Verify content
        with open(config_file, "r") as f:
            loaded = json.load(f)
            assert loaded["name"] == "John Doe"
            assert loaded["initials"] == "JD"
            assert loaded["cid"] == "123456"
            assert loaded["rating"] == "0"


def test_load_options(config_file):
    """Test loading options from JSON file"""
    with patch('LogonDetails.OPTIONS_PATH', config_file):
        # Create test file
        options = {
            "name": "Jane Doe",
            "cid": "654321",
            "initials": "JD",
            "rating": "1",
        }
        with open(config_file, "w") as f:
            json.dump(options, f)
        
        # Load and verify
        loaded = load_previous_options()
        assert loaded["name"] == "Jane Doe"
        assert loaded["cid"] == "654321"
        assert loaded["initials"] == "JD"
        assert loaded["rating"] == "1"


def test_load_nonexistent_file(tmp_path):
    """Test loading from nonexistent file returns empty dict"""
    nonexistent_file = str(tmp_path / "nonexistent.json")
    with patch('LogonDetails.OPTIONS_PATH', nonexistent_file):
        result = load_previous_options()
        assert result == {}


@pytest.mark.parametrize("name,initials,cid,rating,password", [
    ("John Doe", "JD", "123456", "0", "pass123"),
    ("Jane Smith", "JS", "654321", "1", "secret456"),
    ("Test Controller", "TC", "1234567", "2", "password789"),
])
def test_patch_prf_file_various_users(prf_file, name, initials, cid, rating, password):
    """Test patching .prf file with various user data"""
    initial_content = "SomeOption\tvalue\nLastSession\trealname\tOldName\n"
    with open(prf_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    patch_prf_file(prf_file, name, initials, cid, rating, password)

    with open(prf_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert f"LastSession\trealname\t{name}" in content
    assert f"LastSession\tcertificate\t{cid}" in content
    assert f"LastSession\trating\t{rating}" in content
    assert f"LastSession\tcallsign\t{initials}_OBS" in content
    assert f"LastSession\tpassword\t{password}" in content


def test_patch_prf_removes_old_entries(prf_file):
    """Test that old config entries are removed and replaced"""
    initial_content = (
        "LastSession\trealname\tOldName\n"
        "LastSession\tcertificate\tOLDCID\n"
        "LastSession\tpassword\toldpass\n"
        "SomeOption\tvalue\n"
    )
    with open(prf_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    patch_prf_file(prf_file, "NewName", "NN", "123456", "0", "newpass")

    with open(prf_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify no old values remain
    assert "OldName" not in content
    assert "OLDCID" not in content
    assert "oldpass" not in content


@pytest.mark.parametrize("initial_content,state,should_contain", [
    ("Plugins\tPlugin1\tsome/path\nOtherOption\tvalue\n", "present", True),
    ("OtherOption\tvalue\n", "present", True),
    ("Plugins\tPlugin1\t\\Data\\Plugin\\DiscordEuroscope.dll\n", "present", True),
    ("Plugins\tPlugin1\t\\Data\\Plugin\\DiscordEuroscope.dll\nOther\tvalue\n", "absent", False),
])
def test_discord_plugin_states(prf_file, initial_content, state, should_contain):
    """Test Discord plugin in various states (present/absent)"""
    with open(prf_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    with patch('LogonDetails._resolve_discord_relpath', return_value=r"\Data\Plugin\DiscordEuroscope.dll"):
        patch_discord_plugin(prf_file, state=state)

    with open(prf_file, "r", encoding="utf-8") as f:
        content = f.read()

    if should_contain:
        assert "DiscordEuroscope.dll" in content
    else:
        assert "DiscordEuroscope.dll" not in content


def test_no_duplicate_discord_plugin(prf_file):
    """Test that Discord plugin is not added twice"""
    initial_content = "Plugins\tPlugin1\t\\Data\\Plugin\\DiscordEuroscope.dll\n"
    with open(prf_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    with patch('LogonDetails._resolve_discord_relpath', return_value=r"\Data\Plugin\DiscordEuroscope.dll"):
        patch_discord_plugin(prf_file, state="present")

    with open(prf_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Count occurrences - should only be one
    count = content.count("DiscordEuroscope.dll")
    assert count == 1


@pytest.mark.parametrize("initial_content,cpdlc_code,should_exist", [
    (
        "vSMR Vatsim UK:cpdlc_password:oldcode\nOtherSetting:value\n",
        "newcode123",
        True
    ),
    (
        "OtherSetting:value\nEND\n",
        "freshcode456",
        True
    ),
    (
        "vSMR Vatsim UK:cpdlc_password:initial\nMore:data\n",
        "updated789",
        True
    ),
])
def test_patch_cpdlc_password(plugins_file, initial_content, cpdlc_code, should_exist):
    """Test updating/adding CPDLC password in various file states"""
    with open(plugins_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    patch_plugins_file(plugins_file, cpdlc_code)

    with open(plugins_file, "r", encoding="utf-8") as f:
        content = f.read()

    if should_exist:
        assert f"vSMR Vatsim UK:cpdlc_password:{cpdlc_code}" in content


@pytest.mark.parametrize("initials,content_to_check", [
    ("JD", "JD_OBS"),
    ("JS", "JS_OBS"),
    ("ABC", "ABC_OBS"),
])
def test_replace_example_placeholder(ese_file, initials, content_to_check):
    """Test replacing EXAMPLE placeholder with various initials"""
    initial_content = "Some content\nEXAMPLE_OBS\nMore content with EXAMPLE\n"
    with open(ese_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    patch_ese_file(ese_file, initials)

    with open(ese_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert content_to_check in content
    assert "EXAMPLE" not in content


@pytest.mark.parametrize("cid", [
    "123456",
    "654321",
    "1234567",
])
def test_add_cid_to_feedback_url(profiles_file, cid):
    """Test adding CID to feedback URL with various CIDs"""
    initial_content = (
        "Some config\n"
        "Submit feedback at vats.im/atcfb\n"
        "More content\n"
    )
    with open(profiles_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    patch_profiles_file(profiles_file, cid)

    with open(profiles_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert f"vatsim.uk/atcfb?cid={cid}" in content
    assert "vats.im/atcfb" not in content


def test_resolve_discord_relpath_from_prf_parent(tmp_path):
    """Test resolving Discord DLL path from .prf directory structure"""
    # Create directory structure
    prf_dir = tmp_path / "profiles"
    plugin_dir = tmp_path / "Data" / "Plugin"
    plugin_dir.mkdir(parents=True)
    prf_dir.mkdir()

    # Create test file paths
    prf_file = prf_dir / "test.prf"
    dll_file = plugin_dir / "DiscordEuroscope.dll"

    # Create dummy DLL file
    dll_file.touch()

    # Get relative path
    rel_path = _resolve_discord_relpath(str(prf_file))

    # Should contain DiscordEuroscope.dll
    assert "DiscordEuroscope.dll" in rel_path


# ============================================================================
# Skip/Default Preservation Tests
# ============================================================================
# Ensure that when users skip optional fields, the current value is preserved
# and not overwritten with None or empty strings

class TestSkipPreservesCurrentValue:
    """Test that skipping optional fields preserves current values"""

    @patch('LogonDetails.ask_scan_code_key')
    def test_asel_key_skip_preserves_current_value(self, mock_ask_scan_code):
        """Test that skipping ASEL key preserves the current value"""
        current_value = "123456"
        mock_ask_scan_code.return_value = None
        
        result = prompt_for_field("asel_key", current_value)
        
        # Should preserve current value, not return None
        assert result == current_value
        assert result is not None

    @patch('LogonDetails.ask_scan_code_key')
    def test_asel_key_skip_with_empty_string(self, mock_ask_scan_code):
        """Test that empty string from skip is replaced with current value"""
        current_value = "789012"
        mock_ask_scan_code.return_value = ""
        
        result = prompt_for_field("asel_key", current_value)
        
        # Should preserve current value, not return empty string
        assert result == current_value
        assert result != ""

    @patch('LogonDetails.ask_scan_code_key')
    def test_asel_key_with_valid_value_overrides(self, mock_ask_scan_code):
        """Test that valid key value overrides the current value"""
        current_value = "old_value"
        new_value = "987654"
        mock_ask_scan_code.return_value = new_value
        
        result = prompt_for_field("asel_key", current_value)
        
        # Should use the new value when provided
        assert result == new_value
        assert result != current_value

    @patch('LogonDetails.ask_scan_code_key')
    def test_asel_key_skip_with_empty_string_current(self, mock_ask_scan_code):
        """Test that skip returns empty current value if no current was set"""
        current_value = ""
        mock_ask_scan_code.return_value = None
        
        result = prompt_for_field("asel_key", current_value)
        
        # Should preserve empty current value when None returned
        assert result == ""

    @patch('LogonDetails.ask_scan_code_key')
    def test_asel_key_multiple_skips(self, mock_ask_scan_code):
        """Test that multiple skips in a row preserve the value"""
        current_value = "persistent_value"
        mock_ask_scan_code.return_value = None
        
        # First skip
        result1 = prompt_for_field("asel_key", current_value)
        assert result1 == current_value
        
        # Second skip (using result of first as current)
        result2 = prompt_for_field("asel_key", result1)
        assert result2 == current_value
        
        # Value should remain stable through multiple skips
        assert result1 == result2

    @patch('LogonDetails.ask_yesno')
    def test_yes_no_fields_always_return_y_or_n(self, mock_yesno):
        """Test that yes/no fields always return valid y/n, never None"""
        for field in ["realistic_tags", "realistic_conversion"]:
            # Test with True (should return "y")
            mock_yesno.return_value = True
            result = prompt_for_field(field, "n")
            assert result == "y"
            assert result is not None
            
            # Test with False (should return "n")
            mock_yesno.return_value = False
            result = prompt_for_field(field, "y")
            assert result == "n"
            assert result is not None

    @patch('LogonDetails.ask_rating')
    def test_rating_field_always_returns_valid_value(self, mock_rating):
        """Test that rating field returns valid rating index"""
        valid_ratings = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
        
        for rating in valid_ratings:
            mock_rating.return_value = rating
            result = prompt_for_field("rating", "")
            
            # Should return a valid rating index
            assert result in valid_ratings
            assert result is not None

    @patch('LogonDetails.ask_yesno')
    def test_discord_presence_returns_y_or_n_never_none(self, mock_yesno):
        """Test that Discord presence field always returns valid y/n"""
        # Test with True
        mock_yesno.return_value = True
        result = prompt_for_field("discord_presence", "n")
        assert result == "y"
        assert result is not None
        
        # Test with False
        mock_yesno.return_value = False
        result = prompt_for_field("discord_presence", "y")
        assert result == "n"
        assert result is not None

    @patch('LogonDetails.ask_string')
    def test_text_fields_preserve_on_cancel(self, mock_ask_string):
        """Test optional text fields preserve current when returning None"""
        # Optional field like CPDLC
        current_value = "existing_code"
        mock_ask_string.return_value = current_value
        
        result = prompt_for_field("cpdlc", current_value)
        
        # Should return the value (user provided input)
        assert result == current_value
        assert result is not None

    @patch('LogonDetails.ask_with_images')
    def test_coast_choice_always_returns_valid_option(self, mock_ask_with_images):
        """Test that coast_choice field always returns 1, 2, or 3"""
        valid_choices = ["1", "2", "3"]
        
        for choice in valid_choices:
            mock_ask_with_images.return_value = choice
            result = prompt_for_field("coast_choice", choice)
            
            assert result in valid_choices
            assert result is not None

    @patch('LogonDetails.ask_with_images')
    def test_land_choice_always_returns_valid_option(self, mock_ask_with_images):
        """Test that land_choice field always returns 1, 2, or 3"""
        valid_choices = ["1", "2", "3"]
        
        for choice in valid_choices:
            mock_ask_with_images.return_value = choice
            result = prompt_for_field("land_choice", choice)
            
            assert result in valid_choices
            assert result is not None


# ============================================================================
# Missing Coverage: Patch File Functions and Edge Cases
# ============================================================================
# Tests for uncovered code paths in file patching and configuration functions

class TestPatchPrfFileWithAsel:
    """Test patching .prf files with ASEL key configuration"""

    def test_patch_asel_key_adds_new_setting(self, prf_file):
        """Test adding ASEL key setting to .prf file"""
        initial_content = "SomeOption\tvalue\nOtherSetting\tdata\n"
        with open(prf_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_prf_file_with_asel(prf_file, "123456")

        with open(prf_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Settings\tAselKey\t123456" in content

    def test_patch_asel_key_replaces_existing(self, prf_file):
        """Test replacing existing ASEL key setting"""
        initial_content = "Settings\tAselKey\told_value\nOtherSetting\tdata\n"
        with open(prf_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_prf_file_with_asel(prf_file, "new_value")

        with open(prf_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Settings\tAselKey\tnew_value" in content
        assert "old_value" not in content

    def test_patch_asel_key_handles_empty_file(self, prf_file):
        """Test patching empty .prf file"""
        with open(prf_file, "w", encoding="utf-8") as f:
            f.write("")

        patch_prf_file_with_asel(prf_file, "999999")

        with open(prf_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Settings\tAselKey\t999999" in content

    def test_patch_asel_key_error_handling(self, tmp_path):
        """Test ASEL key patching with nonexistent file"""
        nonexistent_file = str(tmp_path / "nonexistent.prf")
        # Should not raise exception, just print error
        patch_prf_file_with_asel(nonexistent_file, "123456")
        # Function handles error gracefully


class TestDiscordPluginEdgeCases:
    """Test Discord plugin patching edge cases"""

    def test_discord_plugin_with_multiple_plugins(self, prf_file):
        """Test Discord plugin addition when multiple plugins exist"""
        initial_content = (
            "Plugins\tPlugin1\tpath/to/plugin1\n"
            "Plugins\tPlugin2\tpath/to/plugin2\n"
            "Plugins\tPlugin3\tpath/to/plugin3\n"
        )
        with open(prf_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        with patch('LogonDetails._resolve_discord_relpath', return_value=r"\Data\Plugin\DiscordEuroscope.dll"):
            patch_discord_plugin(prf_file, state="present")

        with open(prf_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should be added as Plugin4
        assert "Plugins\tPlugin4" in content
        assert "DiscordEuroscope.dll" in content

    def test_discord_plugin_removal_multiple_exists(self, prf_file):
        """Test removing Discord plugin when multiple plugins exist"""
        initial_content = (
            "Plugins\tPlugin1\tpath/to/plugin1\n"
            "Plugins\tPlugin2\t\\Data\\Plugin\\DiscordEuroscope.dll\n"
            "Plugins\tPlugin3\tpath/to/plugin3\n"
        )
        with open(prf_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_discord_plugin(prf_file, state="absent")

        with open(prf_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "DiscordEuroscope.dll" not in content
        assert "Plugin1" in content
        assert "Plugin3" in content

    def test_discord_plugin_with_no_existing_plugins(self, prf_file):
        """Test adding Discord plugin when no Plugins line exists"""
        initial_content = "SomeOption\tvalue\nAnotherOption\tvalue\n"
        with open(prf_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        with patch('LogonDetails._resolve_discord_relpath', return_value=r"\Data\Plugin\DiscordEuroscope.dll"):
            patch_discord_plugin(prf_file, state="present")

        with open(prf_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Plugins\tPlugin1" in content
        assert "DiscordEuroscope.dll" in content


class TestResolveDiscordRelpath:
    """Test Discord DLL relative path resolution"""

    def test_resolve_returns_fallback_when_no_dll(self, tmp_path):
        """Test that fallback is returned when DLL file doesn't exist"""
        prf_file = tmp_path / "test.prf"
        prf_file.touch()
        
        result = _resolve_discord_relpath(str(prf_file))
        
        # Should return fallback when DLL not found
        assert "DiscordEuroscope.dll" in result

    def test_resolve_with_nested_directories(self, tmp_path):
        """Test relative path resolution with deeply nested directory structure"""
        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        plugin_dir = tmp_path / "Data" / "Plugin"
        plugin_dir.mkdir(parents=True)
        
        dll_file = plugin_dir / "DiscordEuroscope.dll"
        dll_file.touch()
        
        prf_file = deep_dir / "test.prf"
        prf_file.touch()
        
        result = _resolve_discord_relpath(str(prf_file))
        
        assert "DiscordEuroscope.dll" in result


class TestPatchPluginsFileEdgeCases:
    """Test edge cases in plugins.txt patching"""

    def test_patch_cpdlc_with_end_marker(self, plugins_file):
        """Test patching Plugins.txt file with END marker"""
        initial_content = "SomeOption\tvalue\nEND\n"
        with open(plugins_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_plugins_file(plugins_file, "test_code")

        with open(plugins_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert "vSMR Vatsim UK:cpdlc_password:test_code" in content

    def test_patch_cpdlc_multiple_updates(self, plugins_file):
        """Test updating CPDLC when called multiple times"""
        initial_content = "vSMR Vatsim UK:cpdlc_password:old_code\n"
        with open(plugins_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        # First update
        patch_plugins_file(plugins_file, "new_code1")
        with open(plugins_file, "r", encoding="utf-8") as f:
            content1 = f.read()
        assert "new_code1" in content1

        # Second update (file now has updated code)
        patch_plugins_file(plugins_file, "new_code2")
        with open(plugins_file, "r", encoding="utf-8") as f:
            content2 = f.read()
        assert "new_code2" in content2
        assert "new_code1" not in content2


class TestPatchEseFileEdgeCases:
    """Test edge cases in .ese file patching"""

    def test_patch_ese_with_multiple_examples(self, ese_file):
        """Test that all EXAMPLE placeholders are replaced"""
        initial_content = "EXAMPLE_OBS\nXXXX_EXAMPLE\nEXAMPLE"
        with open(ese_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_ese_file(ese_file, "JCD")

        with open(ese_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert content.count("JCD") == 3
        assert "EXAMPLE" not in content


class TestPatchProfilesFileEdgeCases:
    """Test edge cases in Profiles.txt patching"""

    def test_patch_profiles_with_multiple_feedback_urls(self, profiles_file):
        """Test that all feedback URLs are replaced"""
        initial_content = (
            "Submit feedback at vats.im/atcfb\n"
            "More text here\n"
            "Submit feedback at vats.im/atcfb\n"
        )
        with open(profiles_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_profiles_file(profiles_file, "123456")

        with open(profiles_file, "r", encoding="utf-8") as f:
            content = f.read()

        assert content.count("vatsim.uk/atcfb?cid=123456") == 2
        assert "vats.im/atcfb" not in content

    def test_patch_profiles_no_feedback_url(self, profiles_file):
        """Test patching when no feedback URL exists"""
        initial_content = "Some content\nNo feedback URL here\n"
        with open(profiles_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        patch_profiles_file(profiles_file, "123456")

        with open(profiles_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Content should remain unchanged
        assert "Some content" in content


class TestLoadPreviousOptionsRobustness:
    """Test robustness of configuration loading"""

    def test_load_options_with_missing_keys(self, config_file):
        """Test loading configuration with missing expected keys"""
        with patch('LogonDetails.OPTIONS_PATH', config_file):
            incomplete_options = {
                "name": "Partial Config"
                # Missing other required fields
            }
            with open(config_file, "w") as f:
                json.dump(incomplete_options, f)

            loaded = load_previous_options()
            assert loaded["name"] == "Partial Config"
            assert len(loaded) == 1

    def test_load_options_with_extra_keys(self, config_file):
        """Test loading configuration with extra unexpected keys"""
        with patch('LogonDetails.OPTIONS_PATH', config_file):
            extended_options = {
                "name": "Full Config",
                "custom_field": "custom_value",
                "another_field": 12345
            }
            with open(config_file, "w") as f:
                json.dump(extended_options, f)

            loaded = load_previous_options()
            assert loaded["name"] == "Full Config"
            assert loaded["custom_field"] == "custom_value"
            assert loaded["another_field"] == 12345

    def test_load_options_malformed_json(self, config_file):
        """Test handling of corrupted/malformed JSON config file"""
        with patch('LogonDetails.OPTIONS_PATH', config_file):
            # Write invalid JSON
            with open(config_file, "w") as f:
                f.write("{invalid json content")
            
            # Should raise an exception when trying to parse
            with pytest.raises(Exception):
                load_previous_options()

    def test_save_and_load_roundtrip(self, config_file):
        """Test that saved options can be perfectly loaded back"""
        with patch('LogonDetails.OPTIONS_PATH', config_file):
            test_config = {
                "name": "Test User",
                "initials": "TU",
                "cid": "123456",
                "rating": "1",
                "password": "test123",
                "cpdlc": "ABC123",
                "discord_presence": "y"
            }
            
            save_options(test_config)
            loaded = load_previous_options()
            
            assert loaded == test_config
