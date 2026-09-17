Dưới đây là toàn bộ nội dung file specification mở rộng **`museum-3d-scene-spec.md`** đã được bổ sung thêm nhiều từ vựng chuyên biệt cho TOEIC (28 từ) và đóng gói vào 1 file Markdown duy nhất để bạn dễ dàng sao chép:

```markdown
# 3D Scene Specification: Museum Tour & Exhibition (박물관 / 미술관)

**Target Feature:** Visual Vocabulary 3D Scene Generator  
**Topic:** Culture, Art, History & Public Venues (`museum-tour-01`)  
**Context:** Active Museum Exhibition Hall with Tour Guide, Visitors, and Artifact Displays  
**Target Vocabulary Count:** 28 TOEIC Terms  
**Engine & Tech Stack Target:** React Three Fiber (R3F), `@react-three/drei`, Three.js, JSON Scene Schema  

---

## 1. Scene Layout & Environment Description

### 1.1 Spatial Grid & Isometric Perspective
* **Perspective:** 3/4 Isometric-style View (Angled Top-Down Projection).
* **Origin (0,0,0):** Center of the main exhibition hall flooring.
* **Orientation:**
  * **Main Wall & Displays:** Located along the back/top-left boundary, featuring framed artwork, information placards, wall-mounted artifacts, audio guide stations, and emergency exits.
  * **Exhibits & Center Objects:** Positioned in the center and midground, including glass display cases, pedestals holding sculptures, velvet rope stanchions, interactive kiosks, and cordoned-off historical relics.
  * **Entities & Activity Area:** Tour guide stands near a central sculpture display holding a pointer, surrounded by a group of attentive visitors/tourists. Security guards monitor the perimeter near the turnstiles and donation box.

### 1.2 Environment & Lighting Configuration
* **Initial Camera Position:** [13.0, 11.0, 15.0]
* **Camera Focus Target:** [0.0, 1.8, 0.0]
* **Field of View (FOV):** 40°
* **Lighting:**
  * **Ambient Light:** Intensity 0.5, Color `#f8f9fa` (Warm ambient gallery lighting).
  * **Directional Light (Spot/Track Lights):** Position [8, 18, 10], Intensity 1.4, Soft directional spotlights targeting key exhibit pieces.

---

## 2. Detailed Object & Vocabulary Mapping

| Object Key | Vocabulary ID | Term / Word | IPA | Category | Description & Scene Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `obj-museum` | `vocab_museum` | museum | `/mjuˈziːəm/` | Context | Interior gallery building displaying historical/artistic items. |
| `obj-exhibit` | `vocab_exhibit` | exhibit / exhibition | `/ɪɡˈzɪbɪt/` | Context | An object or collection on public display in the hall. |
| `obj-guide` | `vocab_guide` | tour guide / docent | `/tʊr ɡaɪd/` | Entity | Docent/guide pointing at an exhibit while addressing visitors. |
| `obj-visitor` | `vocab_visitor` | visitor / tourist / patron | `/ˈvɪzɪtər/` | Entity | Group of spectators observing artwork and listening to guide. |
| `obj-curator` | `vocab_curator` | curator | `/kjʊˈreɪtər/` | Entity | Museum official overseeing art preservation and arrangement. |
| `obj-painting` | `vocab_painting` | painting / artwork / portrait | `/ˈpeɪntɪŋ/` | Display | Framed canvas art hanging on the gallery wall. |
| `obj-sculpture` | `vocab_sculpture` | sculpture / statue / bust | `/ˈskʌlptʃər/` | Display | 3D carved or molded art figure standing on a pedestal. |
| `obj-pedestal` | `vocab_pedestal` | pedestal | `/ˈpedɪstl/` | Display | Raised support base holding a marble sculpture or vase. |
| `obj-display-case` | `vocab_display_case` | display case / showcase | `/dɪˈspleɪ keɪs/` | Display | Glass enclosure protecting fragile historical artifacts. |
| `obj-artifact` | `vocab_artifact` | artifact / relic | `/ˈɑːrtɪfækt/` | Display | Historical object (e.g., ancient pottery, relic) inside display case. |
| `obj-placard` | `vocab_placard` | placard / plaque / label | `/ˈplækɑːrd/` | Display | Information plaque mounted next to artwork explaining its origin. |
| `obj-stanchion` | `vocab_stanchion` | stanchion / velvet rope | `/ˈstænʃn/` | Barrier | Post and velvet rope barrier keeping visitors at a safe distance. |
| `obj-audio-guide` | `vocab_audio_guide` | audio guide | `/ˈɔːdioʊ ɡaɪd/` | Equipment | Handheld device or headphones worn by visitors for narration. |
| `obj-brochure` | `vocab_brochure` | brochure / pamphlet | `/broʊˈʃʊr/` | Item | Paper map/guidebook held by a visitor in the exhibition hall. |
| `obj-ticket` | `vocab_ticket` | admission ticket | `/ədˈmɪʃn ˈtɪkɪt/` | Item | Pass or voucher held by visitors entering the exhibition. |
| `obj-guard` | `vocab_guard` | security guard | `/sɪˈkjʊrəti ɡɑːrd/` | Entity | Staff member standing near the corner ensuring museum rules. |
| `obj-gallery-wall` | `vocab_gallery_wall` | gallery wall | `/ˈɡæləri wɔːl/` | Architecture | Vertical surface painted in neutral tones supporting framed art. |
| `obj-spotlight` | `vocab_spotlight` | spotlight / track light | `/ˈspɑːtlaɪt/` | Fixture | Ceiling track light illuminating specific statues and paintings. |
| `obj-bench` | `vocab_bench` | bench | `/bentʃ/` | Furniture | Seating arrangement in the middle of the room for viewing art. |
| `obj-turnstile` | `vocab_turnstile` | turnstile / entrance gate | `/ˈtɜːrnstaɪl/` | Facility | Mechanical barrier gate at entrance for ticket validation. |
| `obj-kiosk` | `vocab_kiosk` | interactive kiosk | `/ˈkiːɑːsk/` | Equipment | Digital touch-screen terminal providing interactive map & info. |
| `obj-donation-box` | `vocab_donation_box` | donation box | `/doʊˈneɪʃn bɑːks/` | Container | Clear container for voluntary monetary contributions. |
| `obj-cloakroom` | `vocab_cloakroom` | cloakroom / coat check | `/ˈkloʊkruːm/` | Facility | Area where visitors drop off heavy coats and large bags. |
| `obj-souvenir` | `vocab_souvenir` | souvenir / gift shop item | `/ˌsuːvəˈnɪr/` | Item | Miniature replica or postcard purchased at the gift shop counter. |
| `obj-restoration` | `vocab_restoration` | restoration easel | `/ˌrestəˈreɪʃn/` | Equipment | Easel where a conservator cleans or fixes historical paintings. |
| `obj-archway` | `vocab_archway` | archway / hallway | `/ˈɑːrtʃweɪ/` | Architecture | Curved structural opening leading to another exhibition room. |
| `obj-exit` | `vocab_exit` | emergency exit | `/ɪˈmɜːrdʒənsi ˈeksɪt/` | Fixture | Illuminated green doorway sign pointing to safety egress. |
| `obj-mural` | `vocab_mural` | mural | `/ˈmjʊrəl/` | Artwork | Large wall painting executed directly on a gallery surface. |

---

## 3. AI Agent Detailed Scene Prompt

```text
Create a stylized isometric 3D low-poly scene representing a bustling museum exhibition hall.

Core Architectural & Display Features:
- Spacious museum gallery with polished hardwood flooring, track spotlighting, an archway leading to adjacent wings, and a central gallery bench.
- Wall displays including large framed oil portraits, an expansive historical wall mural, and illuminated information plaques mounted alongside each artwork.
- Center displays featuring a marble bust sculpture on a white pedestal, guarded by brass velvet rope stanchions.
- Glass display cases housing ancient pottery artifacts and golden relics on velvet stands.
- Entrance & Facility zone: Turnstile gate, digital interactive kiosk, and a clear donation box near the entry.

Entities & Crowd Activity:
- A docent/tour guide character wearing a badge, holding a pointer rod and explaining an exhibit.
- A group of visitors/patrons listening attentively; some holding printed brochures, others wearing audio guide headsets.
- A curator character inspecting an easel restoration setup near a wall painting.
- A uniform security guard standing near the emergency exit door watching over the room.

Visual Style & Lighting:
- Elegant low-poly aesthetic, neutral beige and off-white gallery walls, rich wood tones, warm directional track lighting casting focused spotlights on exhibits with soft subtle shadows.