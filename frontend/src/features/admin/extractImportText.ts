const MAX_IMPORT_FILE_BYTES = 100 * 1024 * 1024;

/** Extract selectable PDF text for the existing preview parser. */
export async function extractImportText(file: File): Promise<string> {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    throw new Error("Choose a PDF file for import.");
  }
  if (file.size > MAX_IMPORT_FILE_BYTES) {
    throw new Error("Choose a PDF file up to 100 MB.");
  }

  const pdfjs = await import("pdfjs-dist");
  const workerUrl = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  const task = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
  let text = "";
  try {
    const pdf = await task.promise;
    const pages: string[] = [];
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const content = await page.getTextContent();
      let pageText = "";
      for (const item of content.items) {
        if ("str" in item) {
          pageText += item.str;
          if (item.hasEOL) pageText += "\n";
        }
      }
      pages.push(pageText.trim());
    }
    text = pages.join("\n\n");
  } finally {
    await task.destroy();
  }

  if (!text.trim()) {
    throw new Error("No selectable text was found in this PDF. Scanned pages need OCR before import.");
  }
  return text;
}
