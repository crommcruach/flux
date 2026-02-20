"""
WIRESHARK ANALYSIS - What Information to Provide
=================================================

Please capture packets from your WORKING 3rd party tool and provide this info:

STEP 1: In Wireshark
--------------------
1. Filter: udp.port == 6454
2. Capture packets while your 3rd party tool sends to 192.168.1.2
3. Click on ONE packet (any Art-Net packet)

STEP 2: Expand These Sections and Copy Info
-------------------------------------------

Find one ArtDMX packet and provide:

📋 INTERNET PROTOCOL VERSION 4 (IP) SECTION:
   - Source Address: ???.???.???.???
   - Destination Address: ???.???.???.???
   - Time to Live: ???
   - Protocol: UDP (17)
   - Header Length: ???
   - Total Length: ???

📋 USER DATAGRAM PROTOCOL (UDP) SECTION:
   - Source Port: ??????
   - Destination Port: 6454 (should be)
   - Length: ???
   - Checksum: ???

📋 ART-NET SECTION:
   - OpCode: ??? (should be 0x5000 for ArtDMX)
   - Protocol Version: ??? (should be 14)
   - Sequence: ???
   - Physical: ???
   - Universe: ???
   - Length: ???

STEP 3: Check for Multiple Packet Types
---------------------------------------
Look at ALL captured packets and tell me:
   □ How many ArtDMX packets (OpCode 0x5000)?
   □ How many ArtSync packets (OpCode 0x5200)?
   □ How many ArtPoll packets (OpCode 0x2000)?
   □ Any other packet types?

STEP 4: Export Packet Details (BEST OPTION)
-------------------------------------------
Right-click on one packet → Copy → All Visible Items
Then paste the text here

OR

Right-click on one packet → Copy → ...as a Hex Stream
Then paste the hex here

STEP 5: Timing Information
--------------------------
Look at the "Time" column:
   - How many packets per second?
   - Is there a specific pattern (e.g., ArtDMX + ArtSync pairs)?

==================================================
PASTE THIS TEMPLATE WITH YOUR VALUES:
==================================================

IP Layer:
  Source: 
  Destination: 
  TTL: 
  Total Length: 

UDP Layer:
  Source Port: 
  Destination Port: 
  Length: 

Art-Net:
  OpCode: 
  Protocol Version: 
  Sequence: 
  Physical: 
  Universe: 
  DMX Length: 

Packet Types Seen:
  ArtDMX: 
  ArtSync: 
  ArtPoll: 
  Other: 

Packet Rate:
  Packets per second: 

==================================================
"""

print(__doc__)
