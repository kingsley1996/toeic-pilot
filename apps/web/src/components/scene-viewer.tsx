"use client";

import {
  API_ROUTES,
  type VocabularyDetail,
  type VocabularyPage,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { OrbitControls, Html, Line } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ArrowLeft, Check, Eye, Maximize2, Minimize2, RotateCcw, Target, X } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState, type FC, type ReactNode } from "react";
import * as THREE from "three";

import { AccentRow } from "@/components/audio-button";
import {
  Cone,
  SceneMotionContext,
  Signboard,
  WAREHOUSE_SHAPES,
  Worker,
} from "@/components/scene-shapes";
import { Car, URBAN_SHAPES, UrbanEnvironment } from "@/components/scene-shapes-urban";
import {
  CONSTRUCTION_SHAPES,
  ConstructionEnvironment,
} from "@/components/scene-shapes-construction";
import { RESIDENCE_SHAPES, ResidenceEnvironment } from "@/components/scene-shapes-residence";
import type { Patrol, SceneDef, SceneObjectDef, ShapeKey } from "@/content/scenes";
import { apiFetch } from "@/lib/api";
import { Alert, Button, Panel, Skeleton, cx } from "@/components/ui";
import { useToast } from "@/lib/toast";

/*
 * Ba lớp trạng thái, mỗi lớp đúng một chủ (SPEC-VISUAL-VOCAB-3D §3):
 * DOM-overlay ở `SceneViewer`, thế giới 3D ở `SceneCanvas`, và camera ở
 * `CameraRig` — rig giữ mutation trực tiếp trên camera/controls, nên nó không
 * được phép có bạn cùng tầng.
 */

/** Hai bảng shape ghép lại. Thiếu key nào là `tsc` kêu ngay ở đây. */
const SHAPES: Record<ShapeKey, FC> = {
  ...WAREHOUSE_SHAPES,
  ...URBAN_SHAPES,
  ...CONSTRUCTION_SHAPES,
  ...RESIDENCE_SHAPES,
};

const entryKey = (o: { headword: string; partOfSpeech: string }) =>
  `${o.headword}|${o.partOfSpeech}`;

/** Vòng dưới chân object — phản hồi KHÔNG dựa chỉ vào màu (§11): kèm ✓/✗ ở hotspot. */
type ObjectStatus = "idle" | "selected" | "right" | "wrong";

const RING_COLORS: Record<Exclude<ObjectStatus, "idle">, string> = {
  selected: "#c2340f", // chu sa — màu của hành động đang chọn
  right: "#2e7d4f",
  wrong: "#a31220",
};

/**
 * Góc nhìn đầu MẶC ĐỊNH của cảnh. `SceneDef.home` ghi đè được (ngã tư cần khung
 * chặt hơn nhà kho); `Canvas`, `OrbitControls` và nút "về góc nhìn đầu" cùng đọc
 * một chỗ nên không thể lệch nhau.
 */
const HOME_POS: [number, number, number] = [12.2, 9.8, 17.5];
const HOME_LOOK: [number, number, number] = [0, 0.8, 0];

/** `useThree(s => s.controls)` chỉ được khai hình dạng ở đây — không export đi đâu khác. */
type ControlsLike = { target: THREE.Vector3; update: () => void };

export type FlyTarget = {
  pos: [number, number, number];
  dist: number;
  seq: number;
  /** Cao độ nhìn — theo nhãn chứ không theo đất (nhãn trên mái cao 8–10 m). */
  lookY: number;
} | null;

function Ring({ radius, status }: { radius: number; status: ObjectStatus }) {
  if (status === "idle") return null;
  return (
    <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[radius, radius + 0.18, 40]} />
      <meshBasicMaterial color={RING_COLORS[status]} transparent opacity={0.95} />
    </mesh>
  );
}

/**
 * Nhịp đi–về của một `Patrol`: độ lệch theo nửa quãng đường (−1..1) và hướng
 * nó đang quay mặt. Cos nên vận tốc bằng 0 ở hai đầu — đổi hướng tức thời thì
 * xe giật một cái.
 */
function shuttle(phase: number): [number, number] {
  return [Math.sin(phase), Math.cos(phase) >= 0 ? 1 : -1];
}

/**
 * Nhóm biết chạy quanh `at`. Dừng lại là nó trôi về đúng `at` chứ không đỗ
 * tại chỗ đang đứng: camera bay tới `at` khi object được chọn, và recall chấm
 * vào trí nhớ vị trí của người học — hai thứ đó phải cùng một chỗ.
 *
 * Có `patrol` là hướng do vận tốc quyết định, `rotationY` của def bị bỏ qua:
 * mũi của mọi shape chỉ về +X, giữ cả hai cùng xoay là xe chạy lùi.
 */
/**
 * Xe nền nhường người đi bộ: người viết độ lệch VỪA render vào `report`, xe
 * đọc qua `watch` và đứng chờ NGOÀI vạch (`gate`) khi người đang trên đường.
 * Xe đã vào trong vạch thì đi tiếp cho khuất — dừng giữa vạch mới là sai.
 */
function Mover({
  at,
  rotationY = 0,
  patrol,
  animated,
  reportRef,
  watchRef,
  gate,
  children,
}: {
  at: [number, number, number];
  rotationY?: number;
  patrol?: Patrol;
  animated: boolean;
  reportRef?: { current: number };
  watchRef?: { current: number };
  gate?: { at: number; half: number; pedHalf: number };
  children: ReactNode;
}) {
  const ref = useRef<THREE.Group>(null);
  const clock = useRef({ phase: 0, t: 0, home: 1 });

  useFrame((_, dt) => {
    const g = ref.current;
    if (!g || !patrol) return;
    const c = clock.current;
    const rate = 1 - Math.exp(-4 * dt);
    const dir0 = shuttle(c.phase)[1];
    let held = false;
    if (gate && watchRef) {
      const own = (patrol.axis === "x" ? g.position.x : g.position.z) - gate.at;
      const near = Math.abs(own) < gate.half;
      const before = dir0 > 0 ? own < -0.5 : own > 0.5;
      held = near && before && Math.abs(watchRef.current) < gate.pedHalf;
    }
    if (animated && !held) {
      c.phase += (dt * patrol.speed) / patrol.range;
      c.t += dt;
    }
    c.home += ((animated ? 1 : 0) - c.home) * rate;
    const [u, dir] = shuttle(c.phase);
    const off = u * patrol.range * c.home;
    if (reportRef) reportRef.current = off;
    // `yaw` xoay tuyến trong mặt phẳng nền — đường urban chạy chéo nên thiếu
    // nó là xe đi cắt qua vỉa hè. Cùng quy ước với `armPoint`: xoay vector
    // trục bằng rotationY(yaw).
    const yaw = patrol.yaw ?? 0;
    const dx = patrol.axis === "x" ? Math.cos(yaw) : Math.sin(yaw);
    const dz = patrol.axis === "x" ? -Math.sin(yaw) : Math.cos(yaw);
    const [x, y, z] = at;
    g.position.set(x + off * dx, y, z + off * dz);
    const base = patrol.axis === "x" ? 0 : -Math.PI / 2;
    g.rotation.y = yaw + base + (dir > 0 ? 0 : Math.PI);
  });

  return (
    <group ref={ref} position={at} rotation={[0, rotationY, 0]}>
      {children}
    </group>
  );
}

function SceneObject({
  def,
  status,
  labelMode,
  animated,
  reportRef,
  onPick,
}: {
  def: SceneObjectDef;
  status: ObjectStatus;
  labelMode: "pill" | "dot";
  animated: boolean;
  /** Người đi bộ báo độ lệch để xe nền nhường đường (chỉ urban). */
  reportRef?: { current: number };
  onPick: (id: string) => void;
}) {
  const Shape = SHAPES[def.shape];
  const [hovered, setHovered] = useState(false);

  useEffect(() => {
    if (!hovered) return;
    document.body.style.cursor = "pointer";
    return () => {
      document.body.style.cursor = "";
    };
  }, [hovered]);

  return (
    <Mover
      at={def.position}
      rotationY={def.rotationY ?? 0}
      patrol={def.patrol}
      animated={animated}
      reportRef={reportRef}
    >
      <group
        scale={def.scale ?? 1}
        onClick={(e) => {
          e.stopPropagation();
          onPick(def.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
        }}
        onPointerOut={() => setHovered(false)}
      >
        <SceneMotionContext.Provider value={animated}>
          <Shape />
        </SceneMotionContext.Provider>
        <Ring radius={def.ringRadius} status={status} />
        {/* Sợi nối nhãn xuống vật — nhãn treo cao (crosswalk 2.6 m) thì mắt
            không tự biết chữ thuộc về vật nào. Nét đứt màu chu sa cho khỏi lẫn
            vào cảnh xám. Dừng ở MẶT vật (`topY`), không xuyên xuống đất. Chỉ
            explore: recall mà vẽ là lộ đáp án. `raycast` tắt để sợi không bao
            giờ nuốt cú bấm. Nhãn đã thấp thì không vẽ, vẽ là thành nhiễu. */}
        {labelMode === "pill" && def.hotspotY - (def.topY ?? 0.5) >= 0.8 && (
          <group>
            <Line
              points={[
                [0, (def.topY ?? 0.5) + 0.24, 0],
                [0, def.hotspotY - 0.35, 0],
              ]}
              color="#c2340f"
              lineWidth={2}
              dashed
              dashSize={0.18}
              gapSize={0.14}
              raycast={() => null}
            />
            <mesh
              position={[0, (def.topY ?? 0.5) + 0.12, 0]}
              rotation={[Math.PI, 0, 0]}
              raycast={() => null}
            >
              <coneGeometry args={[0.09, 0.24, 10]} />
              <meshBasicMaterial color="#c2340f" />
            </mesh>
          </group>
        )}
        {labelMode === "pill" ? (
          // `pointerEvents` của drei CHỈ có hiệu lực ở chế độ `transform`: truyền
          // vào đây thì nó bị bỏ qua im lặng. Chống nhãn đè nhãn bằng bố cục
          // (vị trí + `hotspotY` trong scene file), không bằng prop.
          <Html position={[0, def.hotspotY, 0]} center distanceFactor={9} zIndexRange={[20, 0]}>
            <button
              type="button"
              data-object-id={def.id}
              onClick={(e) => {
                e.stopPropagation();
                onPick(def.id);
              }}
              aria-pressed={status === "selected"}
              className={cx(
                "whitespace-nowrap rounded border px-2.5 py-1 text-[15px] font-semibold transition-colors",
                // Vật chạy: nhãn của nó không nuốt con trỏ (đây là class Tailwind
                // trên CHÍNH cái nút, khác prop `pointerEvents` của drei — cái đó
                // chỉ ăn ở chế độ `transform`). Pill quét ngang cảnh mà chặn click
                // của hàng xóm thì người học bấm vào chữ mà không thấy gì.
                // Bấm vào thân xe vẫn ăn: mesh có `onClick`.
                def.patrol && "pointer-events-none",
                status === "selected"
                  ? "border-transparent bg-action text-on-action"
                  : status === "right"
                    ? "border-transparent bg-[#2e7d4f] text-white"
                    : status === "wrong"
                      ? "border-transparent bg-[#a31220] text-white"
                      : "border-rule-strong bg-panel text-ink-muted hover:text-ink",
              )}
            >
              {status === "right" && (
                <Check size={12} strokeWidth={2.5} className="mr-0.5 inline" aria-hidden />
              )}
              {status === "wrong" && (
                <X size={12} strokeWidth={2.5} className="mr-0.5 inline" aria-hidden />
              )}
              {def.headword}
            </button>
          </Html>
        ) : (
          // Recall: chấm tròn không chữ — vị trí vẫn phải tìm bằng mắt. `aria-label`
          // có chủ ý: bài kiểm thị giác vô nghĩa với người không nhìn thấy, và
          // đường học của họ là danh sách từ bên dưới (§8.3), không phải chế độ này.
          <Html position={[0, def.hotspotY, 0]} center zIndexRange={[20, 0]} pointerEvents="none">
            <button
              type="button"
              data-object-id={def.id}
              aria-label={def.headword}
              onClick={(e) => {
                e.stopPropagation();
                onPick(def.id);
              }}
              className="pointer-events-auto h-3.5 w-3.5 rounded-pill border-2 border-panel bg-action/80 hover:bg-action"
            />
          </Html>
        )}
      </group>
    </Mover>
  );
}

/** Nhổ neo camera: bay tới `focus` cho tới khi sát, hoặc tới khi người dùng tự xoay. */
function CameraRig({
  focus,
  home,
  homeSeq,
  cancelRef,
}: {
  focus: FlyTarget;
  home: { pos: [number, number, number]; look: [number, number, number] };
  homeSeq: number;
  cancelRef: { current: boolean };
}) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as ControlsLike | null;
  const plan = useRef<{ pos: THREE.Vector3; look: THREE.Vector3 } | null>(null);
  const lastSeq = useRef(-1);
  const lastHome = useRef(0);
  /** Pose của máy quay TRƯỚC khi bay tới một object — "Đóng" trả lại đúng chỗ cũ. */
  const before = useRef<{ pos: THREE.Vector3; look: THREE.Vector3 } | null>(null);
  const touched = useRef(false);

  useFrame((_, dt) => {
    if (cancelRef.current) {
      cancelRef.current = false;
      plan.current = null;
      // Họ tự xoay trong lúc thẻ đang mở thì hướng nhìn mới là ý của họ —
      // bật về pose cũ là giật máy quay ngay dưới tay người dùng.
      if (focus) touched.current = true;
    }
    if (focus && focus.seq !== lastSeq.current) {
      lastSeq.current = focus.seq;
      if (!before.current && controls) {
        before.current = { pos: camera.position.clone(), look: controls.target.clone() };
        touched.current = false;
      }
      const look = new THREE.Vector3(focus.pos[0], focus.lookY, focus.pos[2]);
      const dir = camera.position.clone().sub(look);
      dir.y = Math.max(dir.y, focus.dist * 0.4);
      dir.normalize().multiplyScalar(focus.dist);
      plan.current = { pos: look.clone().add(dir), look };
    } else if (!focus && before.current) {
      const back = touched.current ? null : before.current;
      before.current = null;
      touched.current = false;
      plan.current = back;
    }
    if (homeSeq !== lastHome.current) {
      before.current = null;
      lastHome.current = homeSeq;
      plan.current = {
        pos: new THREE.Vector3(...home.pos),
        look: new THREE.Vector3(...home.look),
      };
    }
    const p = plan.current;
    if (!p || !controls) return;
    // lerp theo hệ số độc lập frame-rate — `t = 1 - e^(-k·dt)`
    const t = 1 - Math.exp(-6 * dt);
    camera.position.lerp(p.pos, t);
    controls.target.lerp(p.look, t);
    controls.update();
    if (camera.position.distanceTo(p.pos) < 0.03 && controls.target.distanceTo(p.look) < 0.03) {
      plan.current = null;
    }
  });
  return null;
}

function Ground() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[30, 30]} />
        <meshStandardMaterial color="#dde2e6" />
      </mesh>
      {/* đường nội bộ — vật trang trí, không bấm được */}
      {/* Đường đúng 30 m trên nền 30 m: từng lệch x = 1 nên nó cụt 1 m ở đầu trái
          và thụt 1 m ra ngoài mép phải. Lề hai vệt sơn dưới cũng lấy mốc giữa 0. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 4.6]} receiveShadow>
        <planeGeometry args={[30, 3.2]} />
        <meshStandardMaterial color="#565e66" />
      </mesh>
      {[-10, -6, -2, 2, 6, 10].map((x) => (
        <mesh key={x} rotation={[-Math.PI / 2, 0, 0]} position={[x, 0.02, 4.6]}>
          <planeGeometry args={[1.4, 0.16]} />
          <meshStandardMaterial color="#f2f3f4" />
        </mesh>
      ))}
    </group>
  );
}

function SceneCanvas({
  scene,
  objects,
  statusOf,
  labelMode,
  walking,
  homeSeq,
  onPick,
  focus,
}: {
  scene: SceneDef;
  objects: SceneObjectDef[];
  statusOf: (id: string) => ObjectStatus;
  labelMode: "pill" | "dot";
  walking: boolean;
  homeSeq: number;
  onPick: (id: string) => void;
  focus: FlyTarget;
}) {
  const cancelRef = useRef(false);
  // `walking` đã gồm điều kiện "đang explore". Vật vừa bấm đứng thêm vì lý do
  // khác: nó phải nằm im trong lúc người học đọc thẻ từ.
  const animated = (id: string) => walking && statusOf(id) !== "selected";
  const home = scene.home ?? { pos: HOME_POS, look: HOME_LOOK };
  // Kênh nhường đường (chỉ urban dùng): người đi bộ báo vị trí, xe nền đọc.
  // Truyền cả ref object, đọc/ghi `.current` chỉ trong `useFrame` — đọc trong
  // render là luật hooks cấm. Warehouse không truyền xuống nên không đổi hành vi.
  const pedBus = useRef(0);
  return (
    <Canvas shadows dpr={[1, 1.75]} camera={{ position: home.pos, fov: 45 }}>
      <color attach="background" args={[scene.sky]} />
      <ambientLight intensity={0.75} />
      <directionalLight
        position={[10, 15, 10]}
        intensity={1.15}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={16}
        shadow-camera-bottom={-16}
      />
      {scene.environment === "residential-yard" ? (
        <ResidenceEnvironment />
      ) : scene.environment === "construction-site" ? (
        <ConstructionEnvironment />
      ) : scene.environment === "urban-intersection" ? (
        <>
          <UrbanEnvironment />
          {/* Xe chạy nền: `car` không có trong bảng 15 từ của spec, nên nó là
              bối cảnh chứ không phải object có nhãn — hai cái xe một chiếc có
              nhãn thì nhãn không còn trỏ vào đâu nữa. Đứng chờ ngoài vạch
              (x = 5.5 ± 3) khi người đi bộ đang trên đường (|lệch| < 2.5 m). */}
          <Mover
            at={[-1.6, 0, 0]}
            patrol={{ axis: "x", range: 7.5, speed: 3.4 }}
            animated={walking}
            watchRef={pedBus}
            gate={{ at: 5.5, half: 3, pedHalf: 2.5 }}
          >
            <Car />
          </Mover>
        </>
      ) : (
        <>
          <Ground />
          <Cone at={[1.6, 0, -2.2]} />
          <Cone at={[4.4, 0, 6.4]} />
          {/* Biển đứng SAU dãy kho (z = -12), nóc 8.8 m nên không vật nào che
              được; `home` phải lùi đủ xa mới thấy hết. yaw 0.53 = phương từ
              biển tới camera. */}
          <Suspense fallback={null}>
            <Signboard at={[-6, 0, -12]} rotationY={0.53} />
          </Suspense>
          {/* Tổ kho: cùng `Mover` như xe courier nên đi chung một nhịp. Tuyến
              của nó nằm trước cửa kho, tránh mọi lối xe. */}
          <Mover
            at={[-4.6, 0, -1.6]}
            patrol={{ axis: "x", range: 1.6, speed: 0.45 }}
            animated={walking}
          >
            <Worker />
          </Mover>
        </>
      )}
      {objects.map((def) => (
        <SceneObject
          key={def.id}
          def={def}
          status={statusOf(def.id)}
          labelMode={labelMode}
          animated={animated(def.id)}
          reportRef={def.id === "obj-pedestrian" ? pedBus : undefined}
          onPick={onPick}
        />
      ))}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.12}
        minDistance={2.2}
        maxDistance={34}
        maxPolarAngle={1.48}
        target={home.look}
        onStart={() => {
          cancelRef.current = true;
        }}
      />
      <CameraRig focus={focus} home={home} homeSeq={homeSeq} cancelRef={cancelRef} />
    </Canvas>
  );
}

type Mode = "explore" | "recall";

function shuffle<T>(items: T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

export function SceneViewer({ scene, token }: { scene: SceneDef; token: string }) {
  const toast = useToast();
  const [summaries, setSummaries] = useState<Map<string, VocabularySummary> | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("explore");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<VocabularyDetail | null>(null);
  const [focus, setFocus] = useState<FlyTarget>(null);
  const [flash, setFlash] = useState<{ id: string; kind: "right" | "wrong" } | null>(null);
  const [homeSeq, setHomeSeq] = useState(0);
  const [recall, setRecall] = useState<{ queue: SceneObjectDef[]; index: number } | null>(null);
  // Xe chạy và linh vật đi tuần là trang trí, nên `prefers-reduced-motion` tắt
  // được nó — cùng luật với CSS ở `globals.css`. Đo một lần lúc mount: `SceneViewer`
  // là `ssr: false` nên `window` có ở đây, và đổi cài đặt giữa phiên thì chưa cần biết.
  const [reducedMotion] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    let alive = true;
    apiFetch<VocabularyPage>(`${API_ROUTES.vocabulary}?topic=${scene.topicSlug}&limit=200`, {
      token,
    })
      .then((page) => {
        if (!alive) return;
        setSummaries(
          new Map(
            page.items.map((s) => [
              entryKey({ headword: s.headword, partOfSpeech: s.part_of_speech }),
              s,
            ]),
          ),
        );
      })
      .catch(() => alive && setResolveError("Không đọc được kho từ vựng cho cảnh này."));
    return () => {
      alive = false;
    };
  }, [scene.topicSlug, token]);

  // Chỉ những object resolve được mới vào cảnh — từ hỏng hiện bằng banner,
  // không âm thầm ẩn hotspot (§2.3).
  const objects = useMemo(() => {
    if (!summaries) return [];
    return scene.objects.filter((o) => summaries.has(entryKey(o)));
  }, [summaries, scene.objects]);
  const missing = useMemo(
    () => (summaries ? scene.objects.filter((o) => !summaries.has(entryKey(o))) : []),
    [summaries, scene.objects],
  );

  const entryIdOf = (def: SceneObjectDef) => summaries?.get(entryKey(def))?.id ?? null;

  // Bộ đếm bay là `ref`, không đọc từ `focus`: đóng thẻ là `focus = null` nên
  // nếu lấy `prev?.seq` thì cú bay kế tiếp tái sử dụng đúng số đó, `CameraRig`
  // coi như không có gì mới và cảnh không zoom vào.
  const flySeq = useRef(0);

  function flyTo(def: SceneObjectDef) {
    flySeq.current += 1;
    // Nhìn vào NHÃN vừa bấm (trừ 0.5 m cho cân khung), không nhìn gốc đất:
    // nhãn mái cao 8–10 m mà nhìn y 0.9 là zoom trượt khỏi vật.
    const lookY = def.position[1] + Math.max(0.9, def.hotspotY - 0.5);
    setFocus({
      pos: def.focus ?? def.position,
      dist: def.focusDistance,
      seq: flySeq.current,
      lookY,
    });
  }

  function closeSheet() {
    setSelectedId(null);
    setDetail(null);
    // `focus = null` là tín hiệu cho `CameraRig` bay về pose trước lúc bấm.
    setFocus(null);
  }

  function startRecall() {
    setMode("recall");
    closeSheet();
    setRecall({ queue: shuffle(objects), index: 0 });
  }

  function exitRecall() {
    setMode("explore");
    setRecall(null);
    setFlash(null);
  }

  async function grade(entryId: string, g: number) {
    try {
      await apiFetch(API_ROUTES.submitReview(entryId), {
        method: "POST",
        body: JSON.stringify({ grade: g }),
        token,
      });
    } catch {
      toast.show({
        title: "Không lưu được lượt chấm",
        description: "Mạng hoặc máy chủ vừa từ chối.",
        tone: "alert",
      });
    }
  }

  async function onPick(objectId: string) {
    const def = objects.find((o) => o.id === objectId);
    if (!def) return;

    if (mode === "explore") {
      setSelectedId(objectId);
      setDetail(null);
      flyTo(def);
      const id = entryIdOf(def);
      if (id) {
        try {
          setDetail(await apiFetch<VocabularyDetail>(API_ROUTES.vocabularyDetail(id), { token }));
        } catch {
          toast.show({ title: "Không tải được mục từ", tone: "alert" });
        }
      }
      return;
    }

    // Recall: một cú bấm = một lượt chấm cho TỪ ĐƯỢC HỎI (không phải từ vừa
    // bấm nhầm — tín hiệu hỏng là "không nhận ra target", SM-2 phải ghi vào
    // đúng thẻ đó). grade 4/5/0/3 là thang của /review.
    if (!recall || flash) return;
    const target = recall.queue[recall.index];
    if (!target) return;
    const ok = target.id === objectId;
    setFlash({ id: objectId, kind: ok ? "right" : "wrong" });
    const entryId = entryIdOf(target);
    if (entryId) await grade(entryId, ok ? 4 : 0);
    window.setTimeout(() => {
      setFlash(null);
      setRecall((r) => (r ? { ...r, index: r.index + 1 } : r));
    }, 750);
  }

  function statusOf(id: string): ObjectStatus {
    if (flash) return flash.id === id ? flash.kind : "idle";
    if (mode === "explore") return selectedId === id ? "selected" : "idle";
    return "idle";
  }

  const recallTarget =
    recall && recall.index < recall.queue.length ? recall.queue[recall.index] : null;
  const recallDone = recall !== null && recall.index >= recall.queue.length;

  // Tiếng báo xin ở đây vì lượt luôn kết thúc bằng một cú bấm — chỗ duy nhất
  // trình duyệt cho phát (`toast.tsx` ghi rõ luật này).
  useEffect(() => {
    if (recallDone) {
      toast.show({
        title: "Xong lượt recall",
        tone: "ok",
        sound: "complete",
        dedupeKey: "scene-recall",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recallDone]);

  const selectedDef = selectedId ? objects.find((o) => o.id === selectedId) : null;

  // Fullscreen là API của nền tảng, không phải thư viện: bật trên chính khung
  // canvas, `fullscreenchange` là chỗ duy nhất nói cho biết nó đang bật hay tắt
  // (Esc của trình duyệt tắt mà không ai báo trước).
  const stageRef = useRef<HTMLDivElement>(null);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    const sync = () => setFullscreen(document.fullscreenElement !== null);
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);

  function toggleFullscreen() {
    const stage = stageRef.current;
    if (!stage) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else
      void stage.requestFullscreen().catch(() => {
        toast.show({ title: "Không vào được toàn màn hình", tone: "alert" });
      });
  }

  function onMastered() {
    if (!detail) return;
    void grade(detail.id, 6).then(() =>
      toast.show({
        title: `Đã đánh dấu thuộc: ${detail.headword}`,
        tone: "ok",
        sound: "complete",
        dedupeKey: "scene-mastered",
      }),
    );
    closeSheet();
  }

  return (
    <div
      ref={stageRef}
      className={cx("flex flex-col gap-4", fullscreen && "h-dvh overflow-y-auto bg-ground p-4")}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/learn/scenes"
          className="inline-flex items-center gap-1.5 text-small text-ink-muted hover:text-ink"
        >
          <ArrowLeft size={14} strokeWidth={2} aria-hidden />
          Danh sách cảnh
        </Link>
        <span className="ml-auto flex gap-2" role="group" aria-label="Chế độ học">
          <Button
            variant={mode === "explore" ? "primary" : "secondary"}
            size="sm"
            aria-pressed={mode === "explore"}
            onClick={() => {
              exitRecall();
            }}
          >
            <Eye size={14} strokeWidth={2} aria-hidden />
            Khám phá
          </Button>
          <Button
            variant={mode === "recall" ? "primary" : "secondary"}
            size="sm"
            aria-pressed={mode === "recall"}
            onClick={startRecall}
            disabled={!summaries || objects.length === 0}
          >
            <Target size={14} strokeWidth={2} aria-hidden />
            Recall
          </Button>
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setHomeSeq((n) => n + 1);
            closeSheet();
          }}
          aria-label="Về góc nhìn đầu"
        >
          <RotateCcw size={14} strokeWidth={2} aria-hidden />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={toggleFullscreen}
          aria-pressed={fullscreen}
          aria-label={fullscreen ? "Thoát toàn màn hình" : "Toàn màn hình"}
        >
          {fullscreen ? (
            <Minimize2 size={14} strokeWidth={2} aria-hidden />
          ) : (
            <Maximize2 size={14} strokeWidth={2} aria-hidden />
          )}
        </Button>
      </div>

      {resolveError && <Alert tone="alert">{resolveError}</Alert>}
      {missing.length > 0 && (
        <Alert tone="warn">
          {missing.length} từ của cảnh chưa có trong kho published — cảnh thiếu object:{" "}
          {missing.map((o) => o.headword).join(", ")}.
        </Alert>
      )}

      <div
        className={cx(
          "relative overflow-hidden rounded border border-rule",
          fullscreen ? "min-h-0 flex-1" : "h-[52vh] min-h-[380px]",
        )}
      >
        <SceneCanvas
          scene={scene}
          objects={objects}
          statusOf={statusOf}
          labelMode={mode === "explore" ? "pill" : "dot"}
          walking={!reducedMotion && mode === "explore"}
          homeSeq={homeSeq}
          onPick={onPick}
          focus={focus}
        />
        {mode === "recall" && recall && recallTarget && (
          // `z-30`: hotspot của vật 3D là `Html` với `zIndexRange` tới 20, nên
          // mọi lớp phủ của cảnh phải cao hơn con số đó.
          <div className="absolute inset-x-0 top-0 z-30 flex items-center justify-center p-3">
            <p className="rounded border border-rule-strong bg-panel px-4 py-2 text-body font-semibold">
              Tìm: <span className="text-action">{recallTarget.headword}</span>{" "}
              <span className="font-normal text-ink-muted">
                ({recall.index + 1}/{recall.queue.length})
              </span>
            </p>
          </div>
        )}
        {mode === "explore" && selectedDef && (
          <Panel className="absolute bottom-3 left-3 z-30 max-h-[calc(100%-1.5rem)] w-[min(24rem,calc(100%-1.5rem))] overflow-y-auto p-4">
            {!detail ? (
              <div className="space-y-2" aria-busy="true">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h2 className="text-subtitle">{detail.headword}</h2>
                  {detail.phonetic && (
                    <span className="font-data text-small text-ink-muted">{detail.phonetic}</span>
                  )}
                  <span className="text-small text-ink-faint">{detail.part_of_speech}</span>
                </div>
                <AccentRow clips={detail.headword_audio} showMissing />
                <p className="text-body">{detail.meaning_vi}</p>
                {detail.example && (
                  <p className="border-l-2 border-rule-strong pl-3 text-small italic text-ink-muted">
                    “{detail.example}”
                    {detail.example_vi && (
                      <span className="mt-0.5 block not-italic text-ink-faint">
                        {detail.example_vi}
                      </span>
                    )}
                  </p>
                )}
                <div className="mt-1 flex gap-2">
                  <Button size="sm" onClick={onMastered}>
                    <Check size={14} strokeWidth={2} aria-hidden />
                    Đã thuộc
                  </Button>
                  <Button size="sm" variant="secondary" onClick={closeSheet}>
                    Đóng
                  </Button>
                </div>
              </div>
            )}
          </Panel>
        )}
        {/* §8.3 spec gốc: bản đọc được cho trình đọc màn hình — dựng từ chính
            scene file. Nằm trong khung cảnh để người học khỏi phải rời mắt khỏi
            vật vừa chạm mà đọc; vẫn là DOM thường nên không mất vì WebGL hỏng. */}
        <details className="absolute right-3 top-3 z-30 max-h-[calc(100%-1.5rem)] w-[min(17rem,calc(100%-1.5rem))] overflow-y-auto rounded border border-rule bg-panel/95 text-small">
          <summary className="cursor-pointer px-3 py-2 font-semibold text-ink-muted hover:text-ink">
            Danh sách từ trong cảnh
          </summary>
          <ul className="space-y-1.5 border-t border-rule px-3 py-2">
            {scene.objects.map((o) => {
              const s = summaries?.get(entryKey(o));
              return (
                <li key={o.id}>
                  <span className="font-semibold">{o.headword}</span>
                  {s?.phonetic && (
                    <span className="ml-1.5 font-data text-ink-faint">{s.phonetic}</span>
                  )}
                  {s && <span className="ml-1.5 text-ink-muted">— {s.meaning_vi}</span>}
                </li>
              );
            })}
          </ul>
        </details>
        {recallDone && <RecallSummary objects={objects} onExit={exitRecall} />}
      </div>
    </div>
  );
}

function RecallSummary({ objects, onExit }: { objects: SceneObjectDef[]; onExit: () => void }) {
  return (
    <div className="absolute inset-0 z-30 grid place-items-center bg-panel/90 px-6 py-12">
      <Panel className="w-full max-w-md p-6 text-center">
        <h2 className="text-subtitle">Xong một lượt recall</h2>
        <p className="mt-2 text-small text-ink-muted">
          {objects.length} từ vừa qua SM-2 — từ nào trật sẽ quay lại sớm hơn bình thường.
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <Button size="sm" onClick={onExit}>
            Khám phá tiếp
          </Button>
          <Link
            href="/learn/review"
            className="inline-flex h-8 items-center rounded border border-rule-strong px-2.5 text-small font-semibold hover:bg-recess"
          >
            Hàng đợi ôn hôm nay
          </Link>
        </div>
      </Panel>
    </div>
  );
}
