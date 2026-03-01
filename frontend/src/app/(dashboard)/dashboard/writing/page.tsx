"use client";

import { WritingEvolutionView } from "@/components/writing";
import { writingEvolutionDummy } from "@/lib/data/writing-evolution-dummy";

export default function WritingPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <WritingEvolutionView data={writingEvolutionDummy} />
    </div>
  );
}
