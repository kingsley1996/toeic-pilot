"use client";

/** Trang TẠM để đo bundle của Pixi. Xoá sau khi đo xong. */
import dynamic from "next/dynamic";

const Lab = dynamic(() => import("./lab"), { ssr: false });

export default function PetLabPage() {
  return <Lab />;
}
