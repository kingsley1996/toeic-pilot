# 3D Scene Specification: Residential House & Garden (정원 / 주택)

**Target Feature:** Visual Vocabulary 3D Scene Generator  
**Topic:** Residential Architecture & Landscaping (`residential-yard-01`)  
**Context:** Two-Story Suburban House with Active Yard Work & Gardening Scene  
**Target Vocabulary Count:** 24 TOEIC Terms  
**Engine & Tech Stack Target:** React Three Fiber (R3F), `@react-three/drei`, Three.js, JSON Scene Schema  

---

## 1. Scene Layout & Environment Description

### 1.1 Spatial Grid & Isometric Perspective
* **Perspective:** 3/4 Isometric-style View (Angled Top-Down Projection).
* **Origin (0,0,0):** Ground level at the center-left corner of the house base.
* **Orientation:**
  * **Main Residential House:** Positioned at the center-left along the X/Z axis, featuring a gabled roof, chimney, balcony, bay window, porch, and attached deck/patio.
  * **Front Yard & Entrance Area:** Positioned at the right foreground/midground, including the mailbox, walkway, and decorative flowerpots.
  * **Lawn & Gardening Area:** Occupies the entire foreground and right perimeter, featuring active characters mowing lawn, watering plants with a hose, digging with a shovel, and trimming hedges.

### 1.2 Environment & Lighting Configuration
* **Initial Camera Position:** [14.0, 12.0, 16.0]
* **Camera Focus Target:** [0.0, 2.0, 0.0]
* **Field of View (FOV):** 38°
* **Lighting:**
  * **Ambient Light:** Intensity 0.7, Color `#ffffff`
  * **Directional Light (Sunlight):** Position [15, 22, 12], Intensity 1.25, Soft Shadows enabled.

---

## 2. Detailed Object & Vocabulary Mapping

| Object Key | Vocabulary ID | Term / Word | IPA | Category | Description & Scene Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `obj-roof` | `vocab_roof` | roof | `/ruːf/` | Structural | Sloped upper covering structure of the two-story house. |
| `obj-tile` | `vocab_tile` | tile | `/taɪl/` | Structural | Individual overlapping clay/slate tiles covering the roof surface. |
| `obj-chimney` | `vocab_chimney` | chimney | `/ˈtʃɪmni/` | Structural | Brick vertical structure extending above roof for smoke discharge. |
| `obj-eaves` | `vocab_eaves` | eaves | `/iːvz/` | Structural | Overhanging lower edges of the roof projecting beyond side walls. |
| `obj-weathervane` | `vocab_weathervane` | weathervane | `/ˈweðərveɪn/` | Exterior | Rooster-shaped wind direction indicator mounted on the roof ridge. |
| `obj-vent` | `vocab_vent` | vent | `/vent/` | Exterior | Small rectangular attic ventilation opening under gable apex. |
| `obj-gutter` | `vocab_gutter` | gutter | `/ˈɡʌtər/` | Structural | Horizontal drainage channel along eaves collecting rainwater. |
| `obj-balcony` | `vocab_balcony` | balcony | `/ˈbælkəni/` | Exterior | Platform projecting from upper floor enclosed by a railing. |
| `obj-bay-window` | `vocab_bay_window` | bay window | `/ˈbeɪ wɪndoʊ/` | Exterior | Window space projecting outward from the main exterior wall. |
| `obj-deck` | `vocab_deck` | deck / patio | `/dek/` | Ground Exterior | Flat wooden outdoor platform attached to the side/rear of the house. |
| `obj-porch` | `vocab_porch` | porch | `/pɔːrtʃ/` | Exterior | Covered shelter projecting in front of the main entrance doorway. |
| `obj-doorway` | `vocab_doorway` | doorway | `/ˈdɔːrweɪ/` | Structure | Entrance frame and door structure leading into the house. |
| `obj-pane` | `vocab_pane` | pane | `/peɪn/` | Exterior | Single sheet of glass within a window frame. |
| `obj-trim` | `vocab_trim` | trim | `/trɪm/` | Exterior | Decorative wooden or synthetic border around windows and doors. |
| `obj-mailbox` | `vocab_mailbox` | mailbox | `/ˈmeɪlbɑːks/` | Fixture | Free-standing post-mounted letterbox near front porch area. |
| `obj-mower` | `vocab_mower` | mower (mow) | `/ˈmoʊər/` | Equipment | Push lawn mower operated by a person clearing weeds on lawn. |
| `obj-weed` | `vocab_weed` | weed | `/wiːd/` | Landscape | Wild overgrown grass patches on the lawn area. |
| `obj-hose` | `vocab_hose` | hose (water / spray) | `/hoʊz/` | Equipment | Flexible garden hose held by character spraying water onto garden. |
| `obj-shovel` | `vocab_shovel` | shovel (dig / bury) | `/ˈʃʌvl/` | Equipment | Hand tool with broad blade held by worker digging a soil hole. |
| `obj-flowerpot` | `vocab_flowerpot` | flowerpot | `/ˈflaʊərpɑːt/` | Decoration | Container with flowering plant resting on garden ground. |
| `obj-shrub` | `vocab_shrub` | shrub / bush | `/ʃrʌb/` | Landscape | Low woody perennial plant located near exterior house wall. |
| `obj-hedge` | `vocab_hedge` | hedge | `/hedʒ/` | Landscape | Boundary row of closely planted bushes being trimmed by worker. |
| `obj-yard` | `vocab_yard` | yard / garden / backyard | `/jɑːrd/` | Context | Open green ground area surrounding the residential structure. |

---

## 3. AI Agent Detailed Scene Prompt

```text
Create a stylized isometric 3D low-poly scene representing a residential two-story house with a vibrant active garden and yard.

Core Architectural & House Features:
- A detailed two-story suburban house with a sloped tiled gabled roof, brick chimney, overhanging eaves, roof gutter, a rooster-shaped weather vane, attic vent, upper floor balcony, protruding bay window, wood deck/patio base, front porch, and detailed glass window panes with decorative wall trims.
- A post-mounted mailbox positioned along the pathway leading to the porch doorway.

Gardening & Yard Activity (Foreground & Surrounding Area):
- A lush green lawn/yard featuring wild weed patches and cultivated flowerpots.
- Four active characters performing garden maintenance tasks:
  1. A person wearing a hat pushing a walk-behind lawn mower across the lawn (mowing weeds).
  2. A girl holding a flexible garden hose spraying water onto the lawn/flowerbeds.
  3. A boy holding a metal shovel digging a hole in the dirt (burying/digging action).
  4. A character at the side trimming a neatly shaped green hedge boundary and shrub bushes.

Visual Style & Lighting:
- Bright low-poly aesthetic, vibrant natural greens, warm beige/wooden house facade tones, terracotta roof tiles, clean directional sunlight with soft shadows cast toward the lower-left.