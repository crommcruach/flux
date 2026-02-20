"""
Wireshark Analysis Guide for Art-Net Issues

This script will help you use Wireshark to identify the exact difference
between your Python/stupidArtnet packets and the working 3rd party tool.
"""

print("="*70)
print("WIRESHARK ANALYSIS GUIDE - Art-Net Debugging")
print("="*70)

print("""
STEP 1: Install Wireshark (if not already installed)
------------------------------------------------------
Download from: https://www.wireshark.org/download.html
Install with default options (includes WinPcap/Npcap for packet capture)

STEP 2: Start Wireshark Capture
--------------------------------
1. Open Wireshark
2. Select your NETWORK ADAPTER that has 192.168.1.x IP
   (probably Ethernet or WiFi - check with ipconfig)
3. Click the blue shark fin icon to start capture
4. Set filter to: udp.port == 6454
   (This shows only Art-Net packets)

STEP 3: Capture Working 3rd Party Tool
---------------------------------------
1. With Wireshark running (filter: udp.port == 6454)
2. Send Art-Net from your 3rd party tool to 192.168.1.2
3. In Wireshark, you should see packets appear
4. Right-click on one packet → Follow → UDP Stream
5. Note the details:
   - Source IP
   - Source Port
   - Destination IP (should be 192.168.1.2)
   - Destination Port (should be 6454)
   - Packet size
   - Look at the "Art-Net" protocol details

STEP 4: Capture Python/stupidArtnet
-----------------------------------
1. Keep Wireshark running
2. Run: python test_artsync.py
3. Check Wireshark - do packets appear?

CRITICAL QUESTIONS TO ANSWER:
------------------------------
A) Do Python packets appear in Wireshark AT ALL?
   YES → Packets are being sent, but receiver ignores them
   NO  → Packets never leave your PC (routing/binding issue)

B) If both appear, COMPARE THE PACKETS:
   - Are source IPs different?
   - Are source ports different?
   - Is packet content different?
   - Are there extra headers/options?
   - Check the Art-Net OpCode (0x5000 for ArtDMX, 0x5200 for ArtSync)

C) Double-click both packets and expand "Internet Protocol Version 4":
   - Check TTL (Time To Live)
   - Check Flags
   - Check Options
   
D) Expand "User Datagram Protocol":
   - Check source port
   - Check checksum

E) Expand "Art-Net":
   - Check sequence number
   - Check universe
   - Check data length
   - Check actual DMX data

STEP 5: Save Captures for Comparison
------------------------------------
1. In Wireshark: File → Export Packet Dissections → As Plain Text
2. Save "working_3rd_party.txt"
3. Save "python_stupidartnet.txt"
4. Compare them side-by-side

COMMON ISSUES FOUND WITH WIRESHARK:
-----------------------------------
1. Source IP different → Binding to wrong adapter
2. TTL too low → Set IP_TTL socket option
3. Source port matters → Some receivers expect specific port
4. Extra Art-Net packets → 3rd party tool sends ArtPoll, etc.
5. Checksum wrong → Socket option issue
6. Fragmented packets → MTU size issue

QUICK WIRESHARK FILTER COMMANDS:
--------------------------------
Show only Art-Net:     artnet
Show only to target:   ip.dst == 192.168.1.2
Show both:            artnet && ip.dst == 192.168.1.2
Show source:          ip.src == YOUR_IP

ALTERNATIVE: Use Command Line Capture
-------------------------------------
If you don't want to use Wireshark GUI:

1. Open PowerShell as Administrator
2. Run: tshark -i ETHERNET_ADAPTER -f "udp port 6454" -V > artnet_capture.txt
3. Run your 3rd party tool
4. Press Ctrl+C to stop
5. Open artnet_capture.txt to analyze

STEP 6: Report Findings
-----------------------
After comparing, look for these specific differences:
□ Source IP address
□ Source port number
□ TTL value
□ Packet fragmentation
□ Art-Net sequence numbers
□ Art-Net OpCodes (ArtDMX vs ArtPoll vs ArtSync)
□ Universe numbering
□ DMX data offset/alignment

""")

print("="*70)
print("READY TO DEBUG?")
print("="*70)
print("\n1. Start Wireshark")
print("2. Filter: udp.port == 6454")
print("3. Run your 3rd party tool → Capture packets")
print("4. Run: python test_artsync.py → Capture packets")
print("5. Compare the two side-by-side")
print("\nThis will show EXACTLY what's different!")
print("="*70)

# Also print current network info
import socket
hostname = socket.gethostname()
print(f"\nYour hostname: {hostname}")
print(f"Your IP addresses:")
try:
    for info in socket.getaddrinfo(hostname, None):
        ip = info[4][0]
        if not ip.startswith('::'):
            print(f"  → {ip}")
except:
    pass

print("\nMake sure you capture on the adapter with 192.168.1.x IP!")
print("="*70)
