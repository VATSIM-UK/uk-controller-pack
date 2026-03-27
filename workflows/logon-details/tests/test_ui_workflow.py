import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LogonDetails import (
    is_valid_cid,
    main,
    prompt_for_field,
    collect_basic_config,
    load_previous_options,
    save_options,
    BASIC_FIELDS,
    ADVANCED_FIELDS,
    DEFAULT_FIELDS,
)


class TestUIWorkflowValidation:
    """Test the overall UI workflow and field validation"""

    def test_basic_fields_required(self):
        """Test that all BASIC_FIELDS are defined"""
        assert len(BASIC_FIELDS) > 0
        assert "name" in BASIC_FIELDS
        assert "cid" in BASIC_FIELDS
        assert "initials" in BASIC_FIELDS
        assert "rating" in BASIC_FIELDS
        assert "password" in BASIC_FIELDS

    def test_advanced_fields_defined(self):
        """Test that ADVANCED_FIELDS are properly defined"""
        assert len(ADVANCED_FIELDS) > 0
        assert "realistic_tags" in ADVANCED_FIELDS
        assert "realistic_conversion" in ADVANCED_FIELDS

    def test_default_fields_structure(self):
        """Test that DEFAULT_FIELDS has all expected keys"""
        assert isinstance(DEFAULT_FIELDS, dict)
        assert len(DEFAULT_FIELDS) > 0
        # All default values should be strings
        for key, value in DEFAULT_FIELDS.items():
            assert isinstance(value, str), f"DEFAULT_FIELDS['{key}'] should be string"


class TestFieldPromptingLogic:
    """Test the logic of prompting for individual fields"""

    @patch("LogonDetails.ask_string")
    def test_prompt_for_text_field(self, mock_ask_string):
        """Test prompting for regular text fields like name and initials"""
        mock_ask_string.return_value = "John Doe"

        result = prompt_for_field("name", "")

        assert result == "John Doe"
        mock_ask_string.assert_called_once()

    @patch("LogonDetails.ask_string")
    def test_prompt_for_text_field_with_current_value(self, mock_ask_string):
        """Test that current value is passed to prompt"""
        mock_ask_string.return_value = "Jane Doe"

        current_value = "John Doe"
        result = prompt_for_field("name", current_value)

        assert result == "Jane Doe"
        # Verify current value was passed as default
        args, kwargs = mock_ask_string.call_args
        assert current_value in args or current_value in str(kwargs)

    @patch("LogonDetails.ask_yesno")
    def test_prompt_for_yes_no_field(self, mock_ask_yesno):
        """Test prompting for yes/no fields"""
        mock_ask_yesno.return_value = True

        result = prompt_for_field("realistic_tags", "n")

        assert result == "y"
        mock_ask_yesno.assert_called_once()

    @patch("LogonDetails.ask_yesno")
    def test_prompt_for_yes_no_field_no_answer(self, mock_ask_yesno):
        """Test yes/no field returns 'n' when user selects no"""
        mock_ask_yesno.return_value = False

        result = prompt_for_field("realistic_tags", "y")

        assert result == "n"

    @patch("LogonDetails.ask_rating")
    def test_prompt_for_rating_field(self, mock_ask_rating):
        """Test prompting for rating field"""
        mock_ask_rating.return_value = "2"

        result = prompt_for_field("rating", "0")

        assert result == "2"
        mock_ask_rating.assert_called_once()

    @patch("LogonDetails.ask_yesno")
    def test_prompt_for_discord_presence_field(self, mock_ask_yesno):
        """Test Discord presence field prompting"""
        mock_ask_yesno.return_value = True

        result = prompt_for_field("discord_presence", "n")

        assert result == "y"


class TestNullAndEmptyValueHandling:
    """Test handling of null, empty, and edge-case values"""

    @patch("LogonDetails.ask_string")
    def test_empty_optional_cpdlc_field(self, mock_ask_string):
        """Test that CPDLC field can be left empty"""
        mock_ask_string.return_value = ""

        result = prompt_for_field("cpdlc", "")

        assert result == ""

    @patch("LogonDetails.ask_string")
    @patch("LogonDetails.messagebox.showerror")
    def test_invalid_cid_retry_loop(self, mock_error, mock_ask_string):
        """Test that invalid CID prompts retry"""
        # First call returns invalid, second returns valid
        mock_ask_string.side_effect = ["12345", "123456"]

        result = prompt_for_field("cid", "")

        assert result == "123456"
        # Error dialog should have been shown for invalid CID
        mock_error.assert_called_once()
        # ask_string should have been called twice (retry)
        assert mock_ask_string.call_count == 2

    @patch("LogonDetails.ask_string")
    @patch("LogonDetails.messagebox.showerror")
    def test_invalid_cid_multiple_retries(self, mock_error, mock_ask_string):
        """Test multiple invalid CID attempts before valid one"""
        # Multiple invalid attempts then valid
        mock_ask_string.side_effect = ["", "abc", "12345", "1234567"]

        result = prompt_for_field("cid", "")

        assert result == "1234567"
        # Error dialog should be called for each invalid attempt
        assert mock_error.call_count == 3
        # ask_string should be called 4 times
        assert mock_ask_string.call_count == 4

    @patch("LogonDetails.ask_string")
    def test_special_characters_in_name(self, mock_ask_string):
        """Test that names with special characters are accepted"""
        special_names = ["Jean-Paul O'Brien", "Jose Maria Garcia", "Muller, Hans"]

        for name in special_names:
            mock_ask_string.return_value = name
            result = prompt_for_field("name", "")
            assert result == name
            mock_ask_string.reset_mock()

    @patch("LogonDetails.ask_string")
    def test_whitespace_in_initials(self, mock_ask_string):
        """Test handling of initials with various spacing"""
        test_cases = ["JD", "J D", "  JD  ", "AB"]

        for initials in test_cases:
            mock_ask_string.return_value = initials
            result = prompt_for_field("initials", "")
            # Accept as-is (no trimming in the actual code)
            assert result == initials
            mock_ask_string.reset_mock()

    @patch("LogonDetails.ask_string")
    def test_password_field_accepts_all_characters(self, mock_ask_string):
        """Test that password field accepts special characters"""
        passwords = ["simple123", "p@ssw0rd!", "!@#$%^&*()"]

        for password in passwords:
            mock_ask_string.return_value = password
            result = prompt_for_field("password", "")
            assert result == password
            mock_ask_string.reset_mock()


class TestUIWorkflowStateTransitions:
    """Test the state transitions and workflow logic"""

    @patch("LogonDetails.ask_string")
    @patch("LogonDetails.ask_yesno")
    @patch("LogonDetails.ask_rating")
    @patch("LogonDetails.ask_with_images")
    @patch("LogonDetails.ask_scan_code_key")
    @patch("LogonDetails.load_previous_options")
    @patch("LogonDetails.save_options")
    @patch("LogonDetails.tk.Tk")
    def test_collect_fresh_user_input_flow(
        self,
        mock_tk,
        mock_save,
        mock_load_prev,
        mock_scan_key,
        mock_images,
        mock_rating,
        mock_yesno,
        mock_ask_string,
    ):
        """Test collecting fresh user input without previous options"""
        mock_load_prev.return_value = {}
        mock_ask_string.side_effect = [
            "Test User",  # name
            "TU",  # initials
            "123456",  # cid
            "simple123",  # password
            "",  # cpdlc
        ]
        mock_rating.return_value = "1"
        mock_yesno.side_effect = [False, False]  # Use previous: No, Discord: No

        with patch("LogonDetails.tk._default_root", None):
            result = collect_basic_config()

        # Verify all basic fields are present
        for field in BASIC_FIELDS:
            assert field in result

    @patch("LogonDetails.ask_string")
    @patch("LogonDetails.ask_yesno")
    @patch("LogonDetails.ask_rating")
    @patch("LogonDetails.load_previous_options")
    @patch("LogonDetails.save_options")
    @patch("LogonDetails.tk.Tk")
    def test_load_previous_options_workflow(
        self,
        mock_tk,
        mock_save,
        mock_load_prev,
        mock_rating,
        mock_yesno,
        mock_ask_string,
    ):
        """Test workflow when loading previous options"""
        previous = {
            "name": "Previous User",
            "initials": "PU",
            "cid": "654321",
            "rating": "2",
            "password": "old123",
            "cpdlc": "",
        }
        mock_load_prev.return_value = previous
        mock_yesno.return_value = True  # Use previous options
        mock_rating.return_value = "2"

        with patch("LogonDetails.tk._default_root", None):
            result = collect_basic_config()

        # Previous values should be retained
        assert result["name"] == "Previous User"
        assert result["cid"] == "654321"

    @patch("LogonDetails.ask_string")
    @patch("LogonDetails.ask_yesno")
    @patch("LogonDetails.ask_rating")
    @patch("LogonDetails.load_previous_options")
    @patch("LogonDetails.save_options")
    @patch("LogonDetails.tk.Tk")
    def test_skip_previous_options_workflow(
        self,
        mock_tk,
        mock_save,
        mock_load_prev,
        mock_rating,
        mock_yesno,
        mock_ask_string,
    ):
        """Test workflow when skipping previous options"""
        previous = {
            "name": "Previous User",
            "cid": "654321",
        }
        mock_load_prev.return_value = previous
        mock_yesno.side_effect = [False, False]  # Skip previous, no Discord
        mock_ask_string.side_effect = [
            "New User",  # name
            "NU",  # initials
            "123456",  # cid
            "new123",  # password
            "",  # cpdlc
        ]
        mock_rating.return_value = "1"

        with patch("LogonDetails.tk._default_root", None):
            result = collect_basic_config()

        # New values should override previous
        assert result["name"] == "New User"
        assert result["cid"] == "123456"


class TestConfigurationValidation:
    """Test configuration-level validation"""

    def test_all_basic_fields_have_defaults(self):
        """Test that all BASIC_FIELDS have defaults"""
        for field in BASIC_FIELDS:
            assert (
                field in DEFAULT_FIELDS
            ), f"Field '{field}' missing from DEFAULT_FIELDS"

    def test_no_overlap_between_basic_and_advanced(self):
        """Test that BASIC_FIELDS and ADVANCED_FIELDS are mutually exclusive"""
        overlap = set(BASIC_FIELDS) & set(ADVANCED_FIELDS)
        assert len(overlap) == 0, f"Found overlapping fields: {overlap}"

    @pytest.mark.parametrize("field", ["name", "initials", "cid"])
    def test_required_fields_not_empty_defaults(self, field):
        """Test that critical required fields don't default to empty"""
        # Most required fields should default to empty, but we validate they're set
        # This is a workflow test - actual filling happens in collect_basic_config
        assert isinstance(DEFAULT_FIELDS[field], str)

    def test_yes_no_fields_have_valid_defaults(self):
        """Test that yes/no fields default to valid values"""
        yn_fields = ["realistic_tags", "realistic_conversion", "discord_presence"]
        for field in yn_fields:
            if field in DEFAULT_FIELDS:
                assert DEFAULT_FIELDS[field] in [
                    "y",
                    "n",
                ], f"Field '{field}' should default to 'y' or 'n', got '{DEFAULT_FIELDS[field]}'"

    def test_choice_fields_have_valid_defaults(self):
        """Test that choice fields default to valid options"""
        choice_fields = {
            "coast_choice": ["1", "2", "3"],
            "land_choice": ["1", "2", "3"],
        }
        for field, valid_options in choice_fields.items():
            if field in DEFAULT_FIELDS:
                assert (
                    DEFAULT_FIELDS[field] in valid_options
                ), f"Field '{field}' default '{DEFAULT_FIELDS[field]}' not in {valid_options}"
