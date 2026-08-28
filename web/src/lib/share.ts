import { toast } from "react-toastify";

const writeClipboard = async (text: string): Promise<void> => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();

  try {
    if (!document.execCommand("copy")) {
      throw new Error("Copy failed");
    }
  } finally {
    document.body.removeChild(textarea);
  }
};

export const isSaysNo = (message: string): boolean => {
  const english =
    /budget alert:/i.test(message) ||
    /exceeds?\s+(?:your|the|stated)?\s*(?:monthly\s+)?[a-z\s]{0,12}budget\b/i.test(
      message
    ) ||
    /above\s+(?:your|the|stated)?\s*(?:monthly\s+)?[a-z\s]{0,12}budget\b/i.test(
      message
    ) ||
    /(?:too\s+(?:expensive|much)|skip(?:ping)?\s+it)/i.test(message);
  const chinese =
    /(?:超(?:过|出).{0,6}预算|超出.*预算|超预算|预算之上|建议不买|考虑替代)/.test(
      message
    ) ||
    /(?:太贵|不建议(?:你)?(?:现在)?(?:购买|买)|换(?:一个|个)?(?:更便宜|平价)?的?(?:选择|替代品)?)/.test(
      message
    );
  return english || chinese;
};

export const shareText = async (
  text: string,
  successMessage: string,
  failureMessage: string
): Promise<void> => {
  try {
    await writeClipboard(text);
    toast.success(successMessage);
  } catch (error) {
    toast.error(failureMessage);
  }
};
