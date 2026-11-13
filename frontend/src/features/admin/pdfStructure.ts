export type CropRegion = { page: number; bbox: number[] };

export function mergeRegions(first: CropRegion[], second: CropRegion[]): CropRegion[] {
  const byPage = new Map<number, number[]>();
  for (const region of [...first, ...second]) {
    const prior = byPage.get(region.page);
    byPage.set(region.page, prior
      ? [Math.min(prior[0], region.bbox[0]), Math.min(prior[1], region.bbox[1]),
         Math.max(prior[2], region.bbox[2]), Math.max(prior[3], region.bbox[3])]
      : [...region.bbox]);
  }
  return [...byPage].sort(([a], [b]) => a - b)
    .map(([page, bbox]) => ({ page, bbox }));
}

export function splitRegions(regions: CropRegion[], y: number): [CropRegion[], CropRegion[]] {
  const index = regions.findIndex((region) =>
    y > region.bbox[1] + 30 && y < region.bbox[3] - 30,
  );
  if (!Number.isFinite(y) || index < 0) {
    throw new Error("Choose a split position at least 30 pt from each crop edge.");
  }
  const region = regions[index];
  return [
    [...regions.slice(0, index),
      { page: region.page, bbox: [region.bbox[0], region.bbox[1], region.bbox[2], y] }],
    [{ page: region.page, bbox: [region.bbox[0], y, region.bbox[2], region.bbox[3]] },
      ...regions.slice(index + 1)],
  ];
}

export function renumberAnswers<T extends { position: number; answer_label: string | null }>(
  questions: T[],
): { questions: T[]; normalizedKey: string } {
  const numbered = questions.map((question, index) => ({ ...question, position: index + 1 }));
  return {
    questions: numbered,
    normalizedKey: numbered.filter((question) => question.answer_label)
      .map((question) => `${question.position}. ${question.answer_label}`).join(", "),
  };
}
