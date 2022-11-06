:: VATSIMUK Automatic logon detail entry

:: Title and disabling echo

@ECHO OFF
TITLE VATSIMUK Automatic Logon Details

:: User inputs

SET /P Name=Enter Name: 
cls
SET /P CID=Enter CID: 
cls
::SET /P Password=Enter Password: 
::cls
:: ^ Password stored in plain text, left commented
SET /P CPDLC=Enter Hoppie's Code: 
cls

:: Add CPDLC code to TopSky
echo %CPDLC%>>"Data/Plugin/TopSky/TopSkyCPDLChoppieCode.txt"

:: Appeding "LastSession" to user input

SET PrfName=LastSession	realname	%Name%
SET PrfCID=LastSession	certificate	%CID%
::SET PrfPassword=LastSession	password	%Password%

:: Adding user detials into profiles

:: Belfast

echo %PrfName%>>"Belfast/Aldergrove SMR.prf"
echo %PrfCID%>>"Belfast/Aldergrove SMR.prf"
::echo %PrfPassword%>>"Belfast/Aldergrove SMR.prf"

echo %PrfName%>>"Belfast/Belfast City SMR.prf"
echo %PrfCID%>>"Belfast/Belfast City SMR.prf"
::echo %PrfPassword%>>"Belfast/Belfast City SMR.prf"

echo %PrfName%>>"Belfast/Belfast.prf"
echo %PrfCID%>>"Belfast/Belfast.prf"
::echo %PrfPassword%>>"Belfast/Belfast.prf"

:: Birmingham

echo %PrfName%>>"Birmingham/Birmingham ATM.prf"
echo %PrfCID%>>"Birmingham/Birmingham ATM.prf"
::echo %PrfPassword%>>"Birmingham/Birmingham ATM.prf"

echo %PrfName%>>"Birmingham/Birmingham Combined.prf"
echo %PrfCID%>>"Birmingham/Birmingham Combined.prf"
::echo %PrfPassword%>>"Birmingham/Birmingham Combined.prf"

echo %PrfName%>>"Birmingham/Birmingham SMR.prf"
echo %PrfCID%>>"Birmingham/Birmingham SMR.prf"
::echo %PrfPassword%>>"Birmingham/Birmingham SMR.prf"

:: Bristol

echo %PrfName%>>"Bristol/Bristol Radar.prf"
echo %PrfCID%>>"Bristol/Bristol Radar.prf"
::echo %PrfPassword%>>"Bristol/Bristol Radar.prf"

echo %PrfName%>>"Bristol/Bristol SMR.prf"
echo %PrfCID%>>"Bristol/Bristol SMR.prf"
::echo %PrfPassword%>>"Bristol/Bristol SMR.prf"

:: Cardiff

echo %PrfName%>>"Cardiff/Cardiff Radar.prf"
echo %PrfCID%>>"Cardiff/Cardiff Radar.prf"
::echo %PrfPassword%>>"Cardiff/Cardiff Radar.prf"

echo %PrfName%>>"Cardiff/Cardiff SMR.prf"
echo %PrfCID%>>"Cardiff/Cardiff SMR.prf"
::echo %PrfPassword%>>"Cardiff/Cardiff SMR.prf"

echo %PrfName%>>"Cardiff/St Athan SMR.prf"
echo %PrfCID%>>"Cardiff/St Athan SMR.prf"
::echo %PrfPassword%>>"Cardiff/St Athan SMR.prf"

:: East Midlands

echo %PrfName%>>"East Midlands/East Midlands APP.prf"
echo %PrfCID%>>"East Midlands/East Midlands APP.prf"
::echo %PrfPassword%>>"East Midlands/East Midlands APP.prf"

echo %PrfName%>>"East Midlands/East Midlands ATM.prf"
echo %PrfCID%>>"East Midlands/East Midlands ATM.prf"
::echo %PrfPassword%>>"East Midlands/East Midlands ATM.prf"

echo %PrfName%>>"East Midlands/East Midlands SMR.prf"
echo %PrfCID%>>"East Midlands/East Midlands SMR.prf"
::echo %PrfPassword%>>"East Midlands/East Midlands SMR.prf"

:: Essex

echo %PrfName%>>"Essex/Cambridge SMR.prf"
echo %PrfCID%>>"Essex/Cambridge SMR.prf"
::echo %PrfPassword%>>"Essex/Cambridge SMR.prf"

echo %PrfName%>>"Essex/Essex Combined.prf"
echo %PrfCID%>>"Essex/Essex Combined.prf"
::echo %PrfPassword%>>"Essex/Essex Combined.prf"

echo %PrfName%>>"Essex/Luton APP.prf"
echo %PrfCID%>>"Essex/Luton APP.prf"
::echo %PrfPassword%>>"Essex/Luton APP.prf"

echo %PrfName%>>"Essex/Luton SMR.prf"
echo %PrfCID%>>"Essex/Luton SMR.prf"
::echo %PrfPassword%>>"Essex/Luton SMR.prf"

echo %PrfName%>>"Essex/Stansted APP.prf"
echo %PrfCID%>>"Essex/Stansted APP.prf"
::echo %PrfPassword%>>"Essex/Stansted APP.prf"

echo %PrfName%>>"Essex/Stansted SMR.prf"
echo %PrfCID%>>"Essex/Stansted SMR.prf"
::echo %PrfPassword%>>"Essex/Stansted SMR.prf"

:: Exeter

echo %PrfName%>>"Exeter/Exeter Combined.prf"
echo %PrfCID%>>"Exeter/Exeter Combined.prf"
::echo %PrfPassword%>>"Exeter/Exeter Combined.prf"

:: Gatwick

echo %PrfName%>>"Gatwick/Gatwick APP.prf"
echo %PrfCID%>>"Gatwick/Gatwick APP.prf"
::echo %PrfPassword%>>"Gatwick/Gatwick APP.prf"

echo %PrfName%>>"Gatwick/Gatwick ATM.prf"
echo %PrfCID%>>"Gatwick/Gatwick ATM.prf"
::echo %PrfPassword%>>"Gatwick/Gatwick ATM.prf"

echo %PrfName%>>"Gatwick/Gatwick Combined.prf"
echo %PrfCID%>>"Gatwick/Gatwick Combined.prf"
::echo %PrfPassword%>>"Gatwick/Gatwick Combined.prf"

echo %PrfName%>>"Gatwick/Gatwick SMR.prf"
echo %PrfCID%>>"Gatwick/Gatwick SMR.prf"
::echo %PrfPassword%>>"Gatwick/Gatwick SMR.prf"

:: Generic

echo %PrfName%>>"Generic/Generic APP.prf"
echo %PrfCID%>>"Generic/Generic APP.prf"
::echo %PrfPassword%>>"Generic/Generic APP.prf"

echo %PrfName%>>"Generic/Generic Combined.prf"
echo %PrfCID%>>"Generic/Generic Combined.prf"
::echo %PrfPassword%>>"Generic/Generic Combined.prf"

echo %PrfName%>>"Generic/Generic SMR.prf"
echo %PrfCID%>>"Generic/Generic SMR.prf"
::echo %PrfPassword%>>"Generic/Generic SMR.prf"

:: Heathrow

echo %PrfName%>>"Heathrow/Heathrow APP.prf"
echo %PrfCID%>>"Heathrow/Heathrow APP.prf"
::echo %PrfPassword%>>"Heathrow/Heathrow APP.prf"

echo %PrfName%>>"Heathrow/Heathrow ATM.prf"
echo %PrfCID%>>"Heathrow/Heathrow ATM.prf"
::echo %PrfPassword%>>"Heathrow/Heathrow ATM.prf"

echo %PrfName%>>"Heathrow/Heathrow Combined.prf"
echo %PrfCID%>>"Heathrow/Heathrow Combined.prf"
::echo %PrfPassword%>>"Heathrow/Heathrow Combined.prf"

echo %PrfName%>>"Heathrow/Heathrow SMR.prf"
echo %PrfCID%>>"Heathrow/Heathrow SMR.prf"
::echo %PrfPassword%>>"Heathrow/Heathrow SMR.prf"

:: Leeds

echo %PrfName%>>"Leeds/Leeds APP.prf"
echo %PrfCID%>>"Leeds/Leeds APP.prf"
::echo %PrfPassword%>>"Leeds/Leeds APP.prf"

echo %PrfName%>>"Leeds/Leeds Combined.prf"
echo %PrfCID%>>"Leeds/Leeds Combined.prf"
::echo %PrfPassword%>>"Leeds/Leeds Combined.prf"

echo %PrfName%>>"Leeds/Leeds SMR.prf"
echo %PrfCID%>>"Leeds/Leeds SMR.prf"
::echo %PrfPassword%>>"Leeds/Leeds SMR.prf"

:: Liverpool

echo %PrfName%>>"Liverpool/Liverpool APP.prf"
echo %PrfCID%>>"Liverpool/Liverpool APP.prf"
::echo %PrfPassword%>>"Liverpool/Liverpool APP.prf"

echo %PrfName%>>"Liverpool/Liverpool ATM.prf"
echo %PrfCID%>>"Liverpool/Liverpool ATM.prf"
::echo %PrfPassword%>>"Liverpool/Liverpool ATM.prf"

echo %PrfName%>>"Liverpool/Liverpool Combined.prf"
echo %PrfCID%>>"Liverpool/Liverpool Combined.prf"
::echo %PrfPassword%>>"Liverpool/Liverpool Combined.prf"

echo %PrfName%>>"Liverpool/Liverpool SMR.prf"
echo %PrfCID%>>"Liverpool/Liverpool SMR.prf"
::echo %PrfPassword%>>"Liverpool/Liverpool SMR.prf"

:: London Control
:: AC - Default

echo %PrfName%>>"London Control/AC - Default/Bandbox.prf"
echo %PrfCID%>>"London Control/AC - Default/Bandbox.prf"
::echo %PrfPassword%>>"London Control/AC - Default/Bandbox.prf"

echo %PrfName%>>"London Control/AC - Default/Central.prf"
echo %PrfCID%>>"London Control/AC - Default/Central.prf"
::echo %PrfPassword%>>"London Control/AC - Default/Central.prf"

echo %PrfName%>>"London Control/AC - Default/North.prf"
echo %PrfCID%>>"London Control/AC - Default/North.prf"
::echo %PrfPassword%>>"London Control/AC - Default/North.prf"

echo %PrfName%>>"London Control/AC - Default/South Central.prf"
echo %PrfCID%>>"London Control/AC - Default/South Central.prf"
::echo %PrfPassword%>>"London Control/AC - Default/South Central.prf"

echo %PrfName%>>"London Control/AC - Default/South.prf"
echo %PrfCID%>>"London Control/AC - Default/South.prf"
::echo %PrfPassword%>>"London Control/AC - Default/South.prf"

echo %PrfName%>>"London Control/AC - Default/West.prf"
echo %PrfCID%>>"London Control/AC - Default/West.prf"
::echo %PrfPassword%>>"London Control/AC - Default/West.prf"

:: AC - NERC

echo %PrfName%>>"London Control/AC - NERC/Bandbox (TopSky).prf"
echo %PrfCID%>>"London Control/AC - NERC/Bandbox (TopSky).prf"
::echo %PrfPassword%>>"London Control/AC - NERC/Bandbox (TopSky).prf"

echo %PrfName%>>"London Control/AC - NERC/Bandbox.prf"
echo %PrfCID%>>"London Control/AC - NERC/Bandbox.prf"
::echo %PrfPassword%>>"London Control/AC - NERC/Bandbox.prf"

echo %PrfName%>>"London Control/AC - NERC/Central (TopSky).prf"
echo %PrfCID%>>"London Control/AC - NERC/Central (TopSky).prf"
::echo %PrfPassword%>>"London Control/AC - NERC/Central (TopSky).prf"

echo %PrfName%>>"London Control/AC - NERC/Central.prf"
echo %PrfCID%>>"London Control/AC - NERC/Central.prf"
::echo %PrfPassword%>>"London Control/AC - NERC/Central.prf"

echo %PrfName%>>"London Control/AC - NERC/North (TopSky).prf"
echo %PrfCID%>>"London Control/AC - NERC/North (TopSky).prf"
::echo %PrfPassword%>>"London Control/AC - NERC/North (TopSky).prf"

echo %PrfName%>>"London Control/AC - NERC/North.prf"
echo %PrfCID%>>"London Control/AC - NERC/North.prf"
::echo %PrfPassword%>>"London Control/AC - NERC/North.prf"

echo %PrfName%>>"London Control/AC - NERC/South (TopSky).prf"
echo %PrfCID%>>"London Control/AC - NERC/South (TopSky).prf"
::echo %PrfPassword%>>"London Control/AC - NERC/South (TopSky).prf"

echo %PrfName%>>"London Control/AC - NERC/South Central (TopSky).prf"
echo %PrfCID%>>"London Control/AC - NERC/South Central (TopSky).prf"
::echo %PrfPassword%>>"London Control/AC - NERC/South Central (TopSky).prf"

echo %PrfName%>>"London Control/AC - NERC/South Central.prf"
echo %PrfCID%>>"London Control/AC - NERC/South Central.prf"
::echo %PrfPassword%>>"London Control/AC - NERC/South Central.prf"

echo %PrfName%>>"London Control/AC - NERC/South.prf"
echo %PrfCID%>>"London Control/AC - NERC/South.prf"
::echo %PrfPassword%>>"London Control/AC - NERC/South.prf"

echo %PrfName%>>"London Control/AC - NERC/West (TopSky).prf"
echo %PrfCID%>>"London Control/AC - NERC/West (TopSky).prf"
::echo %PrfPassword%>>"London Control/AC - NERC/West (TopSky).prf"

echo %PrfName%>>"London Control/AC - NERC/West.prf"
echo %PrfCID%>>"London Control/AC - NERC/West.prf"
::echo %PrfPassword%>>"London Control/AC - NERC/West.prf"

:: LTC

echo %PrfName%>>"London Control/LTC/TC Bandbox.prf"
echo %PrfCID%>>"London Control/LTC/TC Bandbox.prf"
::echo %PrfPassword%>>"London Control/LTC/TC Bandbox.prf"

echo %PrfName%>>"London Control/LTC/TC North.prf"
echo %PrfCID%>>"London Control/LTC/TC North.prf"
::echo %PrfPassword%>>"London Control/LTC/TC North.prf"

echo %PrfName%>>"London Control/LTC/TC South.prf"
echo %PrfCID%>>"London Control/LTC/TC South.prf"
::echo %PrfPassword%>>"London Control/LTC/TC South.prf"

:: Manchester

echo %PrfName%>>"Manchester/Manchester APP.prf"
echo %PrfCID%>>"Manchester/Manchester APP.prf"
::echo %PrfPassword%>>"Manchester/Manchester APP.prf"

echo %PrfName%>>"Manchester/Manchester ATM.prf"
echo %PrfCID%>>"Manchester/Manchester ATM.prf"
::echo %PrfPassword%>>"Manchester/Manchester ATM.prf"

echo %PrfName%>>"Manchester/Manchester Combined.prf"
echo %PrfCID%>>"Manchester/Manchester Combined.prf"
::echo %PrfPassword%>>"Manchester/Manchester Combined.prf"

echo %PrfName%>>"Manchester/Manchester SMR.prf"
echo %PrfCID%>>"Manchester/Manchester SMR.prf"
::echo %PrfPassword%>>"Manchester/Manchester SMR.prf"

:: Newcastle

echo %PrfName%>>"Newcastle/Newcastle APP.prf"
echo %PrfCID%>>"Newcastle/Newcastle APP.prf"
::echo %PrfPassword%>>"Newcastle/Newcastle APP.prf"

echo %PrfName%>>"Newcastle/Newcastle Combined.prf"
echo %PrfCID%>>"Newcastle/Newcastle Combined.prf"
::echo %PrfPassword%>>"Newcastle/Newcastle Combined.prf"

echo %PrfName%>>"Newcastle/Newcastle SMR.prf"
echo %PrfCID%>>"Newcastle/Newcastle SMR.prf"
::echo %PrfPassword%>>"Newcastle/Newcastle SMR.prf"

:: Oxford

echo %PrfName%>>"Oxford/Oxford Combined.prf"
echo %PrfCID%>>"Oxford/Oxford Combined.prf"
::echo %PrfPassword%>>"Oxford/Oxford Combined.prf"

:: Scottish
:: Aberdeen

echo %PrfName%>>"Scottish/Aberdeen SMR.prf"
echo %PrfCID%>>"Scottish/Aberdeen SMR.prf"
::echo %PrfPassword%>>"Scottish/Aberdeen SMR.prf"

echo %PrfName%>>"Scottish/Aberdeen.prf"
echo %PrfCID%>>"Scottish/Aberdeen.prf"
::echo %PrfPassword%>>"Scottish/Aberdeen.prf"

:: Edinburgh

echo %PrfName%>>"Scottish/Edinburgh SMR.prf"
echo %PrfCID%>>"Scottish/Edinburgh SMR.prf"
::echo %PrfPassword%>>"Scottish/Edinburgh SMR.prf"

echo %PrfName%>>"Scottish/Edinburgh.prf"
echo %PrfCID%>>"Scottish/Edinburgh.prf"
::echo %PrfPassword%>>"Scottish/Edinburgh.prf"

:: Glasgow

echo %PrfName%>>"Scottish/Glasgow SMR.prf"
echo %PrfCID%>>"Scottish/Glasgow SMR.prf"
::echo %PrfPassword%>>"Scottish/Glasgow SMR.prf"

echo %PrfName%>>"Scottish/Glasgow.prf"
echo %PrfCID%>>"Scottish/Glasgow.prf"
::echo %PrfPassword%>>"Scottish/Glasgow.prf"

:: Area

echo %PrfName%>>"Scottish/Area/Area (TopSky).prf"
echo %PrfCID%>>"Scottish/Area/Area (TopSky).prf"
::echo %PrfPassword%>>"Scottish/Area/Area (TopSky).prf"

echo %PrfName%>>"Scottish/Area/Area.prf"
echo %PrfCID%>>"Scottish/Area/Area.prf"
::echo %PrfPassword%>>"Scottish/Area/Area.prf"

:: Solent

echo %PrfName%>>"Solent/Bournemouth SMR.prf"
echo %PrfCID%>>"Solent/Bournemouth SMR.prf"
::echo %PrfPassword%>>"Solent/Bournemouth SMR.prf"

echo %PrfName%>>"Solent/Solent Radar.prf"
echo %PrfCID%>>"Solent/Solent Radar.prf"
::echo %PrfPassword%>>"Solent/Solent Radar.prf"

echo %PrfName%>>"Solent/Southampton SMR.prf"
echo %PrfCID%>>"Solent/Southampton SMR.prf"
::echo %PrfPassword%>>"Solent/Southampton SMR.prf"

:: Thames

echo %PrfName%>>"Thames/Biggin ADC.prf"
echo %PrfCID%>>"Thames/Biggin ADC.prf"
::echo %PrfPassword%>>"Thames/Biggin ADC.prf"

echo %PrfName%>>"Thames/London City ADC.prf"
echo %PrfCID%>>"Thames/London City ADC.prf"
::echo %PrfPassword%>>"Thames/London City ADC.prf"

echo %PrfName%>>"Thames/Thames APP.prf"
echo %PrfCID%>>"Thames/Thames APP.prf"
::echo %PrfPassword%>>"Thames/Thames APP.prf"

echo %PrfName%>>"Thames/Thames Combined.prf"
echo %PrfCID%>>"Thames/Thames Combined.prf"
::echo %PrfPassword%>>"Thames/Thames Combined.prf"

:: Finish

echo Logon details process complete
pause