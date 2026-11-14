export type OptimizedImage = {
  file: File;
  originalBytes: number;
  optimizedBytes: number;
};

const MAX_IMAGE_EDGE = 1920;
const IMAGE_QUALITY = 0.82;

function replaceExtension(filename: string, extension: string) {
  const dot = filename.lastIndexOf(".");
  const stem = dot > 0 ? filename.slice(0, dot) : filename;
  return stem + extension;
}

export async function optimizeEvidenceImage(file: File): Promise<OptimizedImage> {
  if (!file.type.startsWith("image/")) {
    return {
      file,
      originalBytes: file.size,
      optimizedBytes: file.size,
    };
  }

  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));

    if (scale === 1 && file.size <= 1_500_000 && file.type === "image/webp") {
      return {
        file,
        originalBytes: file.size,
        optimizedBytes: file.size,
      };
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return {
        file,
        originalBytes: file.size,
        optimizedBytes: file.size,
      };
    }

    context.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/webp", IMAGE_QUALITY);
    });

    if (!blob || blob.size >= file.size) {
      return {
        file,
        originalBytes: file.size,
        optimizedBytes: file.size,
      };
    }

    const optimizedFile = new File(
      [blob],
      replaceExtension(file.name || "evidencia", ".webp"),
      {
        type: "image/webp",
        lastModified: Date.now(),
      },
    );

    return {
      file: optimizedFile,
      originalBytes: file.size,
      optimizedBytes: optimizedFile.size,
    };
  } finally {
    bitmap.close();
  }
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}
