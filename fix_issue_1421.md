# Pull Request for Frequency Update in Aldergrove Radar

## Summary

This pull request updates the frequency for EGAA_APP from 133.125 to 133.130 in response to NOTAM I1315/26.

## Changes Implemented

Changes have been made in the following files:
1. `Voice_Scottish.txt` - The frequency for Aldergrove Radar is updated.
2. `Belfast(EGAC & EGAA).json` - Modified the frequency for EGAA_APP to match the new requirement.

## Affected Files and Modifications

### 1. **UK/Data/Settings/Voice_Scottish.txt**

**Before:**
```plaintext
EGAA_APP 133.125
```

**After:**
```plaintext
EGAA_APP 133.130
```

### 2. **_vATIS/Belfast(EGAC & EGAA).json**

**Before:**
```json
{
    "functions": {
        "Approach": {
            "EGAA_APP": {
                "frequency": "133.125"
            }
        }
    }
}
```

**After:**
```json
{
    "functions": {
        "Approach": {
            "EGAA_APP": {
                "frequency": "133.130"
            }
        }
    }
}
```

## Validation

To ensure that the changes comply with the NOTAM I1315/26, I verified the amended designation against the official document. After confirming the accuracy of the changes, the amendments are reflected accurately.

## Test Cases

1. **Test Frequency Changes in `Voice_Scottish.txt`:**
   - Confirm that `EGAA_APP` now uses frequency `133.130`.
   
2. **Test Frequency Accuracy in `_vATIS/Belfast.json`:**
   - Ensure JSON parses correctly.
   - Verify that the frequency for `EGAA_APP` is now set to `133.130`.

### Example Test Case Code (Pseudo-code)

```python
def test_frequency_update_in_voice_scottish():
    with open('UK/Data/Settings/Voice_Scottish.txt') as file:
        assert "EGAA_APP 133.130" in file.readlines()

def test_frequency_update_in_belfast_json():
    with open('_vATIS/Belfast(EGAC & EGAA).json') as file:
        data = json.load(file)
        assert data['functions']['Approach']['EGAA_APP']['frequency'] == "133.130"
```

## Conclusion

The frequency updates align with the NOTAM I1315/26. All updates are made in the relevant locations and verified. These changes ensure that the frequency is correctly reflected across all necessary configurations.