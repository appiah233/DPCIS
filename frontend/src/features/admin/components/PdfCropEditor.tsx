import { useEffect, useRef, useState, type PointerEvent } from "react";

import { AuthenticatedPdfImage } from "@/components/exam/AuthenticatedPdfImage";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { updateQuestionCrops } from "@/features/admin/adminApi";
import type { ParsedQuestion } from "@/types/adminExam";

type Region = { page: number; bbox: number[] };

interface Props {
  examId: string;
  question: ParsedQuestion;
  pageDimensions: Array<[number, number]>;
  onUpdated: (regions: Region[], imageUrls: string[]) => void;
}

export function PdfCropEditor({ examId, question, pageDimensions, onUpdated }: Props) {
  const [regions, setRegions] = useState<Region[]>(question.image_regions ?? []);
  const [dpi, setDpi] = useState(200);
  const [padding, setPadding] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const regionsRef = useRef(regions);
  regionsRef.current = regions;

  useEffect(() => setRegions(question.image_regions ?? []), [question.image_regions]);

  const commit = async (next: Region[]) => {
    if (!question.source_file_id || !question.source_number) return;
    setSaving(true);
    setError(null);
    try {
      const result = await updateQuestionCrops(
        examId, question.source_file_id, question.source_number, next, dpi, padding,
      );
      setRegions(result.regions);
      onUpdated(result.regions, result.image_urls);
    } catch (reason) {
      setRegions(question.image_regions ?? []);
      setError(reason instanceof Error ? reason.message : "Crop update failed.");
    } finally {
      setSaving(false);
    }
  };

  const startDrag = (event: PointerEvent<HTMLButtonElement>, index: number, edge: "top" | "bottom") => {
    if (saving) return;
    const image = event.currentTarget.parentElement?.querySelector("img");
    const imageHeight = image?.getBoundingClientRect().height ?? 0;
    if (imageHeight < 20) return;
    event.preventDefault();
    const initial = regionsRef.current.map((region) => ({ ...region, bbox: [...region.bbox] }));
    const startY = event.clientY;
    const scale = (initial[index].bbox[3] - initial[index].bbox[1]) / imageHeight;
    const move = (pointer: globalThis.PointerEvent) => {
      const next = initial.map((region) => ({ ...region, bbox: [...region.bbox] }));
      const pageHeight = pageDimensions[next[index].page - 1]?.[1] ?? 10000;
      const delta = (pointer.clientY - startY) * scale;
      if (edge === "top") {
        next[index].bbox[1] = Math.max(0, Math.min(next[index].bbox[3] - 30, initial[index].bbox[1] + delta));
      } else {
        next[index].bbox[3] = Math.min(pageHeight, Math.max(next[index].bbox[1] + 30, initial[index].bbox[3] + delta));
      }
      setRegions(next);
      regionsRef.current = next;
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      void commit(regionsRef.current);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
  };

  const nudgeEdge = (index: number, edge: "top" | "bottom", direction: number) => {
    const next = regions.map((region) => ({ ...region, bbox: [...region.bbox] }));
    const pageHeight = pageDimensions[next[index].page - 1]?.[1] ?? 10000;
    if (edge === "top") {
      next[index].bbox[1] = Math.max(0, Math.min(next[index].bbox[3] - 30,
        next[index].bbox[1] + direction * 2));
    } else {
      next[index].bbox[3] = Math.min(pageHeight, Math.max(next[index].bbox[1] + 30,
        next[index].bbox[3] + direction * 2));
    }
    void commit(next);
  };

  const addRegion = () => {
    const lastPage = regions.at(-1)?.page ?? 0;
    const nextPage = lastPage + 1;
    const size = pageDimensions[nextPage - 1];
    if (!size) { setError("No later page is available for this question."); return; }
    void commit([...regions, { page: nextPage, bbox: [0, 0, size[0], Math.min(size[1], 200)] }]);
  };

  return (
    <div className="mt-3 space-y-3">
      {regions.map((region, index) => (
        <div key={`${region.page}-${index}`} className="space-y-1">
          <p className="text-xs text-muted-foreground">Page {region.page}, top {region.bbox[1].toFixed(1)} pt, bottom {region.bbox[3].toFixed(1)} pt</p>
          <div className="relative border border-border">
            {question.image_urls?.[index] ? (
              <AuthenticatedPdfImage path={question.image_urls[index]} alt={question.question_text} className="h-auto w-full max-w-full" />
            ) : null}
            <button type="button" disabled={saving} onPointerDown={(event) => startDrag(event, index, "top")}
              onKeyDown={(event) => { if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                event.preventDefault(); nudgeEdge(index, "top", event.key === "ArrowUp" ? -1 : 1);
              } }}
              className="absolute inset-x-0 top-0 h-4 cursor-ns-resize border-t-4 border-primary bg-primary/10 focus-visible:outline-2 focus-visible:outline-primary"
              aria-label={`Drag top crop edge for page ${region.page}`} />
            <button type="button" disabled={saving} onPointerDown={(event) => startDrag(event, index, "bottom")}
              onKeyDown={(event) => { if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                event.preventDefault(); nudgeEdge(index, "bottom", event.key === "ArrowUp" ? -1 : 1);
              } }}
              className="absolute inset-x-0 bottom-0 h-4 cursor-ns-resize border-b-4 border-primary bg-primary/10 focus-visible:outline-2 focus-visible:outline-primary"
              aria-label={`Drag bottom crop edge for page ${region.page}`} />
          </div>
          {regions.length > 1 ? <Button type="button" variant="outline" disabled={saving}
            onClick={() => void commit(regions.filter((_, itemIndex) => itemIndex !== index))}>Remove page {region.page} region</Button> : null}
        </div>
      ))}
      <div className="flex flex-wrap items-end gap-2">
        <Button type="button" variant="outline" disabled={saving} onClick={addRegion}>Add next page region</Button>
        <Label className="flex flex-col gap-1">DPI <input className="w-24 rounded border p-2" type="number" min={72} max={300} value={dpi} onChange={(event) => setDpi(Number(event.target.value))} /></Label>
        <Label className="flex flex-col gap-1">Padding (pt) <input className="w-24 rounded border p-2" type="number" min={0} max={30} step={1} value={padding} onChange={(event) => setPadding(Number(event.target.value))} /></Label>
        <Button type="button" variant="outline" disabled={saving} onClick={() => void commit(regions)}>Regenerate crops</Button>
      </div>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
