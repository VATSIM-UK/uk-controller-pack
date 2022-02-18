# Data Section

The data section is to allow us to commit changes to be propagated across many ASR/PRF files.

## Fix display logic

ASR fix display on all radar ASRs should follow the ASR 1-4 profile system.

Fixes are sourced from the active sector file Navaids (https://github.com/VATSIM-UK/UK-Sector-File/tree/main/Navaids). VOR/NDBs are excluded, along with FIXES_Old.txt.

All 5 letter fixes are then accepted, unless they are found in fixes_exclude.txt. 

All Non-UK fixes (FIXES_Non-UK.txt) are excluded unless found in fixes_include.txt.