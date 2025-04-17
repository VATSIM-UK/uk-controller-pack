#pragma once

#ifndef MAESTROapi
#define MAESTROapi __declspec ( dllimport )
#endif

extern "C" MAESTROapi bool IsInSequence( const char * callsign ) ;
// return value: true if the callsign (case sensitive!) is found in the sequence
//               false otherwise

extern "C" MAESTROapi double GetCurrentDelay( const char * callsign ) ;
// return value: current (remaining) delay in minutes if the callsign (case sensitive!) is found in the sequence
//               0 otherwise

extern "C" MAESTROapi double GetTotalDelay( const char * callsign ) ;
// return value: total delay in minutes if the callsign (case sensitive!) is found in the sequence
//               0 otherwise
