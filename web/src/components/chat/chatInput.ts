import { config } from "../../config/appConfig";

export const convertToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("Failed to read the file."));
    reader.readAsDataURL(file);
  });
};

export const base64ToBlob = (base64: string): Blob => {
  const base64WithoutPrefix = base64.split(",")[1];
  const binaryString = atob(base64WithoutPrefix);
  const byteArray = new Uint8Array(binaryString.length);

  for (let index = 0; index < binaryString.length; index++) {
    byteArray[index] = binaryString.charCodeAt(index);
  }

  return new Blob([byteArray], { type: "image/png" });
};

export const createImagePreview = (base64: string): string =>
  window.URL.createObjectURL(base64ToBlob(base64));

export const validateImageFile = (
  file: File,
  translate: (key: string, options?: Record<string, unknown>) => string
): string | null => {
  const maxSizeMB = config.features.imageUpload.maxSize;
  if (file.size > maxSizeMB * 1024 * 1024) {
    return translate("errors.fileTooLarge", { size: maxSizeMB });
  }
  if (!config.features.imageUpload.allowedTypes.includes(file.type)) {
    return translate("errors.invalidImageType");
  }
  return null;
};
