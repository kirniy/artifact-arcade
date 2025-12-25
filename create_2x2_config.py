#!/usr/bin/env python3
"""
Generate NovaStar DH418 config for 2x2 panel layout (128x128)
Based on existing 1x3 layout (64x192)

Snake pattern wiring:
  [2] TOP-LEFT  ───→  [3] TOP-RIGHT
       ↑                    │
       │                    ↓
  [1] BOT-LEFT        [4] BOT-RIGHT
       ↑
    INPUT from DH418
"""

import re
import zipfile
import shutil
from pathlib import Path

# Paths
EXTRACTED_DIR = Path("/Users/kirniy/dev/modular-arcade/rcfgx_extracted")
ORIGINAL_XML = EXTRACTED_DIR / "current.xml"
ORIGINAL_BIN = EXTRACTED_DIR / "current.bin"
OUTPUT_DIR = Path("/Users/kirniy/dev/modular-arcade/new_config")
OUTPUT_XML = OUTPUT_DIR / "current.xml"
OUTPUT_BIN = OUTPUT_DIR / "current.bin"
OUTPUT_RCFGX = Path("/Users/kirniy/dev/modular-arcade/2x2_128x128.rcfgx")

# Module template for 2x2 layout
MODULE_TEMPLATE = '''      <ModuleInIrRegularCabinet>
        <ModuleProperty>
          <Name>3</Name>
          <ModuleVersion>2.0</ModuleVersion>
          <ModulePixelCols>64</ModulePixelCols>
          <ModulePixelRows>64</ModulePixelRows>
          <_decodeTypePro>0</_decodeTypePro>
          <ScanType>Scan_32</ScanType>
          <OEPolarity>LowEnable</OEPolarity>
          <DecType>ICN2012WEA</DecType>
          <DataDirectType>Horizontal</DataDirectType>
          <DataGroup>2</DataGroup>
          <DataGroupSequence>AAECAwQFBgc=</DataGroupSequence>
          <ScanABCDCode>AAECAwQFBgcICQoLDA0ODw==</ScanABCDCode>
          <NewScanABCDCode>AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</NewScanABCDCode>
          <ScanABCDCodeSpecila>AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</ScanABCDCodeSpecila>
          <RGBCode>AAECAw==</RGBCode>
          <TotalPointInTable>64</TotalPointInTable>
          <PointTableData>AAABAAIAAwAEAAUABgAHAAgACQAKAAsADAANAA4ADwAQABEAEgATABQAFQAWABcAGAAZABoAGwAcAB0AHgAfACAAIQAiACMAJAAlACYAJwAoACkAKgArACwALQAuAC8AMAAxADIAMwA0ADUANgA3ADgAOQA6ADsAPAA9AD4APwA=</PointTableData>
          <RowsCtrlByDataGroup>ICAgICAgICA=</RowsCtrlByDataGroup>
          <ScreenDriveType>Concurrent</ScreenDriveType>
          <LineBias>0</LineBias>
          <StartPositionOfDataGroup>ACAAAAAAAAA=</StartPositionOfDataGroup>
          <SerialColorNum>0</SerialColorNum>
          <SerialDotsNumPerColor>0</SerialDotsNumPerColor>
          <SerialRGBCode>AgEAAA==</SerialRGBCode>
          <ChipMinLawRepeatNumber>1</ChipMinLawRepeatNumber>
          <ChannelEnableData>AAA=</ChannelEnableData>
          <ChannelData>AAA=</ChannelData>
          <ChipNumber>1</ChipNumber>
          <IsIrregular>0</IsIrregular>
          <DriverChipType>
            <ChipCode>81</ChipCode>
            <IsCabinetToolChip>false</IsCabinetToolChip>
          </DriverChipType>
          <DriverChipTypeExtend>0</DriverChipTypeExtend>
          <DriverTypePro>1</DriverTypePro>
          <DecodeTypePro>0</DecodeTypePro>
          <MainVersion>1</MainVersion>
          <BVersion>0</BVersion>
          <CVersion>0</CVersion>
        </ModuleProperty>
        <HubIndex>0</HubIndex>
        <XInCabinet>{x}</XInCabinet>
        <YInCabinet>{y}</YInCabinet>
        <PixelColInCabinet>64</PixelColInCabinet>
        <PixelRowInCabinet>64</PixelRowInCabinet>
        <GroupInfoInCabinet>
          <ModuleGroupInCabinet>
            <groupIndex>{group1}</groupIndex>
            <connectIndex>0</connectIndex>
            <hubIndex>-1</hubIndex>
          </ModuleGroupInCabinet>
          <ModuleGroupInCabinet>
            <groupIndex>{group2}</groupIndex>
            <connectIndex>0</connectIndex>
            <hubIndex>-1</hubIndex>
          </ModuleGroupInCabinet>
        </GroupInfoInCabinet>
        <IsSector>false</IsSector>
        <SectorPoint>
          <X>0</X>
          <Y>0</Y>
        </SectorPoint>
      </ModuleInIrRegularCabinet>'''

# 2x2 snake pattern layout:
# Signal flow: DH418 → Panel1 → Panel2 → Panel3 → Panel4
#
# Visual layout (as seen from FRONT):
#   Panel2 (top-left)  → Panel3 (top-right)
#      ↑                    ↓
#   Panel1 (bot-left)    Panel4 (bot-right)
#      ↑
#   INPUT
#
# In pixel coordinates (0,0 is top-left):
#   Panel2: X=0, Y=0 (top-left), groups [2,3]
#   Panel3: X=64, Y=0 (top-right), groups [4,5]
#   Panel4: X=64, Y=64 (bot-right), groups [6,7]
#   Panel1: X=0, Y=64 (bot-left), groups [0,1] - INPUT

MODULES_2X2 = [
    # Panel 1: bottom-left (INPUT)
    {"x": 0, "y": 64, "group1": 0, "group2": 1},
    # Panel 2: top-left
    {"x": 0, "y": 0, "group1": 2, "group2": 3},
    # Panel 3: top-right
    {"x": 64, "y": 0, "group1": 4, "group2": 5},
    # Panel 4: bottom-right
    {"x": 64, "y": 64, "group1": 6, "group2": 7},
]


def generate_modules_xml():
    """Generate XML for 4 modules in 2x2 layout"""
    modules = []
    for m in MODULES_2X2:
        modules.append(MODULE_TEMPLATE.format(**m))
    return "\n".join(modules)


def modify_xml(content: str) -> str:
    """Modify the XML content for 2x2 layout"""

    # 1. Update main dimensions
    content = re.sub(r"<Width>64</Width>", "<Width>128</Width>", content, count=1)
    content = re.sub(r"<Height>192</Height>", "<Height>128</Height>", content, count=1)
    content = re.sub(r"<ModuleCols>1</ModuleCols>", "<ModuleCols>2</ModuleCols>", content, count=1)
    content = re.sub(r"<ModuleRows>3</ModuleRows>", "<ModuleRows>2</ModuleRows>", content, count=1)
    content = re.sub(r"<PhysicalDataGroupNum>6</PhysicalDataGroupNum>", "<PhysicalDataGroupNum>8</PhysicalDataGroupNum>", content)
    content = re.sub(r"<LogicalDataGroupNum>8</LogicalDataGroupNum>", "<LogicalDataGroupNum>8</LogicalDataGroupNum>", content)  # Keep same

    # 2. Replace ModuleListInCabinet with new 2x2 modules
    modules_xml = generate_modules_xml()

    # Find and replace the entire ModuleListInCabinet section
    pattern = r"<ModuleListInCabinet>.*?</ModuleListInCabinet>"
    replacement = f"<ModuleListInCabinet>\n{modules_xml}\n    </ModuleListInCabinet>"
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    return content


def generate_point_table_128x128():
    """
    Generate PointTableData for 128x128 display.
    The original has complex mapping, but we'll try with simple sequential mapping.
    If this doesn't work, we may need to analyze the binary more carefully.
    """
    import base64
    import struct

    # For 128x128 with 8 data groups, we need mapping for 16384 pixels
    # Each entry in PointTableData seems to be pixel coordinate mapping
    # Format appears to be: series of (x, y) pairs as 16-bit values

    # For now, we'll create a simple linear mapping and see if it works
    # The original table has complex values that may need reverse engineering

    # Each row in the table: 8 bytes = 4x 16-bit values per pixel
    # Total 128 lines * 8 bytes = 1024 bytes for each group

    # Actually looking at original, it's much more complex
    # Let's just keep the original bin file and only update dimensions
    return None


def main():
    print("=== Creating 2x2 Config for NovaStar DH418 ===\n")

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Read original XML
    print(f"Reading: {ORIGINAL_XML}")
    with open(ORIGINAL_XML, "r", encoding="utf-8") as f:
        xml_content = f.read()

    # Modify XML
    print("Modifying XML for 2x2 layout (128x128)...")
    new_xml = modify_xml(xml_content)

    # Save modified XML
    print(f"Writing: {OUTPUT_XML}")
    with open(OUTPUT_XML, "w", encoding="utf-8") as f:
        f.write(new_xml)

    # Copy the binary file (contains point tables - keep original for now)
    print(f"Copying: {ORIGINAL_BIN} -> {OUTPUT_BIN}")
    shutil.copy(ORIGINAL_BIN, OUTPUT_BIN)

    # Create .rcfgx (ZIP archive)
    print(f"\nCreating: {OUTPUT_RCFGX}")
    with zipfile.ZipFile(OUTPUT_RCFGX, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(OUTPUT_XML, "current.xml")
        zf.write(OUTPUT_BIN, "current.bin")

    print("\n✅ Done!")
    print(f"\nConfig file ready: {OUTPUT_RCFGX}")
    print("\nTo upload:")
    print("1. In NovaLCT: Screen Configuration → Receiving Card")
    print("2. Click 'Load from File' (or 'Import')")
    print(f"3. Select: {OUTPUT_RCFGX}")
    print("4. Click 'Send to Hardware'")


if __name__ == "__main__":
    main()
