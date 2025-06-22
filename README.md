# VjLooper

VjLooper is a Blender add-on that generates procedural animations using configurable signals and presets.

## Installation
1. Copy the add-on folder into Blender's add-ons directory (`scripts/addons`).
2. Enable "VjLooper" from Blender's preferences.

## Basic Usage
- Select an object and create signals from the "VjLooper" panel in the sidebar.
- Configure signal type, amplitude, frequency and other parameters.
- Optionally save and load signal presets.

## Compatibility

| OS | Blender 3.6 LTS | Blender 4.1 | Blender 4.2 Alpha |
|----|-----------------|-------------|-------------------|
| Linux | ✓ | ✓ | ✓ |
| Windows | ✓ | ✓ | ✓ |

If you are running a Blender version older than 3.6 some features may not be fully supported.

## Apply With Offset

![Apply with Offset](docs/apply_offset.gif)

## Loop Lock

1. Enable **Loop Lock** in the Misc section.
2. Adjust animation parameters.
3. Frequencies will snap so that loops close perfectly.

## Randomize Signals
Each animation has fields "Amp Min", "Amp Max", "Freq Min" and "Freq Max".
Set these ranges and press **Randomize** to assign random amplitude and frequency values within them.
