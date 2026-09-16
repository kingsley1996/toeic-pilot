# Feature Specification: Interactive 3D Visual Vocabulary Scene

**Project:** TOEIC Pilot  
**Feature Name:** Interactive 3D Visual Vocabulary Scene (Visual Vocab 3D)  
**Status:** Draft / Proposal  
**Author:** AI Engineering & System Architecture Team  
**Tech Stack Baseline:** React / Next.js, React Three Fiber (R3F), `@react-three/drei`, Three.js, TailwindCSS, Zustand / React Context, Spaced Repetition System (SM-2 integration).

---

## 1. Executive Summary & Product Vision

### 1.1 Overview
The **Interactive 3D Visual Vocabulary Scene** bridges the gap between traditional illustrated vocabulary books (e.g., contextual scene-based diagrams) and modern interactive learning platforms. Instead of flat 2D images or isolated flashcards, learners interact with fully navigable, interactive 3D contextual micro-environments where real-world objects map directly to TOEIC vocabulary words.

### 1.2 Core Philosophy
* **Not a 3D Game:** No heavy game mechanics (physics controllers, collisions, WASD player movement).
* **Not a Flat 3D Flashcard:** Avoids simple card flipping in a 3D canvas.
* **Contextual Learning Hub:** Connects high-frequency TOEIC vocabulary through meaningful spatial relationships (e.g., *pothole*, *guard railing*, *puddle*, *taxi cab*, *cone* together in a single `Road & Traffic` scene).

---

## 2. Technical Stack & Architecture

### 2.1 Technology Choices
* **Rendering Engine:** React Three Fiber (R3F) + Three.js
* **Helper Libraries:** `@react-three/drei` (OrbitControls, Html, useGLTF, Float, Outlines, Preload)
* **3D Assets:** Compact `.glb` / `.gltf` files (optimized low-poly models with Draco compression)
* **UI/HUD Overlays:** Standard React / TailwindCSS overlaying the `<Canvas>`
* **State Management:** Zustand (handling scene state, current mode, camera focal targets, user progress)
* **SRS Engine:** TOEIC Pilot Core SM-2 / Leitner Algorithm DB

### 2.2 Architectural Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AI Scene Planner Agent                          │
│        (Generates scene JSON schema based on topic & target vocab)    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Output JSON
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Scene Renderer Core                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    React Three Fiber Canvas                      │  │
│  │  - Orbit Controls   - Dynamic Hotspots   - Object Highlighting   │  │
│  └────────────────────────────────┬─────────────────────────────────┘  │
│                                   │ Object Click / Select               │
└───────────────────────────────────┼────────────────────────────────────┘
                                    │ vocabularyId
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   TOEIC Pilot Core Vocabulary DB                       │
│      (Audio TTS/Human, IPA, Vietnamese Meaning, Examples, Collocations)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Progress Data
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     SRS Spaced Repetition Engine                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The 6-Level Contextual Learning Loop

To ensure maximum retention, each 3D Scene supports a 6-stage structured learning experience:

```
[Level 1: Observe] ──► [Level 2: Explore] ──► [Level 3: Learn]
                                                      │
[Level 6: Review]  ◄── [Level 5: Context] ◄── [Level 4: Recall]
```

1. **Level 1 — Observe (Wide Shot):** Camera executes an ambient cinematic pan across the scene. Learners observe the complete visual context without UI distractions.
2. **Level 2 — Explore (Interactive Discovery):** Hotspots/3D markers appear over objects. Learners freely rotate, zoom, and click objects in 3D space.
3. **Level 3 — Learn (Deep Inspection):** Selecting an object moves the camera close (smooth transition). Word details appear: IPA, Audio playback, Vietnamese translation, and TOEIC sample sentence.
4. **Level 4 — Recall (Find-the-Object Mode):** Prompts: *"Find the pothole"*. Learners must click the corresponding 3D object in the environment (visual-to-concept recall).
5. **Level 5 — Context (Sentence Completion):** Prompts: *"The taxi hit a ______ on the road."* Learner selects/clicks the corresponding 3D item or types the answer.
6. **Level 6 — Review (SRS Synchronization):** Vocabulary mastery scores are updated and fed directly into the system's global Spaced Repetition System (SM-2).

---

## 4. Data Structures & Schema Definitions

### 4.1 Scene Definition Schema (`scene.json`)

```json
{
  "id": "scene-road-traffic-01",
  "title": "Road & Traffic",
  "category": "Transportation",
  "difficulty": "A2-B1",
  "version": "1.0",
  "environment": {
    "backgroundColor": "#eef2f6",
    "ambientLightIntensity": 0.7,
    "directionalLight": {
      "position": [10, 15, 10],
      "intensity": 1.2,
      "castShadow": true
    },
    "camera": {
      "initialPosition": [8, 6, 12],
      "target": [0, 0, 0],
      "fov": 45
    }
  },
  "assets": {
    "baseScene": "/assets/3d/scenes/road_base.glb"
  },
  "objects": [
    {
      "id": "obj-pothole-01",
      "vocabularyId": "vocab_pothole_001",
      "modelPath": "/assets/3d/objects/pothole.glb",
      "transform": {
        "position": [1.2, 0.01, -2.4],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0, 0.4, 0],
        "label": "Pothole"
      },
      "cameraFocus": {
        "position": [3.0, 2.5, -1.0],
        "target": [1.2, 0.0, -2.4]
      }
    },
    {
      "id": "obj-taxi-01",
      "vocabularyId": "vocab_taxi_cab_002",
      "modelPath": "/assets/3d/objects/taxi.glb",
      "transform": {
        "position": [-1.5, 0.0, 0.5],
        "rotation": [0, 0.785, 0],
        "scale": [1.2, 1.2, 1.2]
      },
      "hotspot": {
        "offset": [0, 1.5, 0],
        "label": "Taxi cab"
      },
      "cameraFocus": {
        "position": [0.5, 2.0, 3.0],
        "target": [-1.5, 0.5, 0.5]
      }
    },
    {
      "id": "obj-traffic-cone-01",
      "vocabularyId": "vocab_cone_003",
      "modelPath": "/assets/3d/objects/cone.glb",
      "transform": {
        "position": [0.5, 0.0, -1.0],
        "rotation": [0, 0, 0],
        "scale": [0.8, 0.8, 0.8]
      },
      "hotspot": {
        "offset": [0, 0.8, 0],
        "label": "Cone"
      },
      "cameraFocus": {
        "position": [2.0, 1.5, 0.5],
        "target": [0.5, 0.2, -1.0]
      }
    }
  ]
}
```

### 4.2 Associated Vocabulary Data (Existing Vocabulary DB)

```json
{
  "id": "vocab_pothole_001",
  "word": "pothole",
  "ipa": "/ˈpɑːthoʊl/",
  "partOfSpeech": "noun",
  "meaningVi": "ổ gà (trên đường)",
  "audioUrl": "https://assets.toeicpilot.com/audio/pothole.mp3",
  "exampleSentence": "The taxi driver swerved to avoid hitting a deep pothole on the street.",
  "collocations": ["hit a pothole", "deep pothole", "pothole repair"],
  "toeicPart5Example": {
    "question": "The city council announced plans to repair several large _____ on Main Street before winter.",
    "options": ["potholes", "puddles", "railings", "gutters"],
    "answer": "potholes"
  }
}
```

---

## 5. AI Agent Integration: Scene Generation Workflow

The TOEIC Pilot AI Agent automates scene configuration so developers do not need to construct JSX manually for every new scene.

```
┌────────────────────────────────────────────────────────┐
│                   Input Prompt / Curriculum             │
│   "Topic: Traffic & Road Accidents | Level: A2-B1"     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   AI Scene Planner                     │
│ 1. Queries Vocabulary DB for relevant TOEIC terms      │
│ 2. Groups items into coherent visual scene             │
│ 3. Assigns spatial coordinates & camera angles         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Schema Validator Agent                   │
│ 1. Checks bounds & overlapping transforms              │
│ 2. Validates vocabulary IDs against DB                 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Output: scene.json                    │
└────────────────────────────────────────────────────────┘
```

### Agent Prompts & Task Rules
1. **Topic Identification:** Agent maps high-frequency TOEIC vocabulary to a single physical space.
2. **Object Placement Rules:** Ensures bounding boxes do not collide or obscure each other.
3. **Focus Point Calculation:** Computes optimal camera offsets for small items (e.g., *empty can*, *gravel*) versus large items (*taxi*, *guard railing*).

---

## 6. UI/UX Interface Design & User Flow

### 6.1 Layout Overview
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ← Exit Scene  │  Road & Traffic (Scene 3/10)              Progress: 8/15  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                            [ 3D R3F Canvas ]                                 │
│                                                                              │
│                                     [ 🚧 Cone ]                              │
│                [ 🚕 Taxi ]               │                                   │
│                     │                    │                                   │
│                     ▼                    ▼                                   │
│                   ( 🚕 )               ( 🚧 )                                │
│                                                                              │
│                                ( 🕳️ Pothole )                                │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │ Selected: POTHOLE /ˈpɑːthoʊl/ [ 🔊 Listen ]                         │   │
│   │ Meaning: Ổ gà (trên đường)                                           │   │
│   │ Example: "The car hit a deep pothole near the intersection."         │   │
│   │ Action: [ Mark as Mastered ]   [ + Add to Review ]                   │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Mode Switching
* **Explore Mode:** Hotspots are visible; clicking an object moves camera and opens Vocabulary Bottom Sheet.
* **Recall / Quiz Mode:** Top banner displays target word (*"Find: guard railing"*). Hotspots hide labels. Clicking the correct object plays success feedback (`Audio + Green Outline`).

---

## 7. Implementation Roadmap & MVP Scope

| Phase | Milestone | Scope / Deliverables |
|---|---|---|
| **Phase 1** | **Core Canvas & Renderer** | Setup R3F canvas, OrbitControls, dynamic GLB loading from `scene.json`. |
| **Phase 2** | **Interactivity & Camera Controls** | Object hover outlines, smooth camera lerping to target coordinates (`useFrame` or `GSAP`). |
| **Phase 3** | **UI Overlay & DB Integration** | Integrate Zustand store with TOEIC Pilot API; render bottom sheet card on object selection. |
| **Phase 4** | **Recall Mode & Quiz Engine** | Implement Level 4 & 5 interaction logic (find-the-object, score tracking). |
| **Phase 5** | **AI Agent Pipeline & Polish** | Auto-generating `scene.json` from prompt inputs; assets optimization with Draco compression. |

---

## 8. Non-Functional Requirements & Performance Targets

1. **Asset Size Limit:** Individual object `.glb` assets $\le 150\text{KB}$; full scene bundle $\le 2.5\text{MB}$.
2. **Target Frame Rate:** Stable $60\text{ fps}$ on desktop; $\ge 45\text{ fps}$ on mid-range mobile browsers.
3. **Accessibility:** Screen-reader fallback text list available for all 3D scene terms.
4. **Offline Support:** Asset caching via Service Worker for repeat learning sessions.