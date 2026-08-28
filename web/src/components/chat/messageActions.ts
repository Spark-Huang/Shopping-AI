import { toast } from "react-toastify";
import { shareText } from "../../lib/share";

export const shareMessage = async (
  text: string,
  successMessage: string,
  failureMessage: string
): Promise<void> => {
  try {
    if (navigator.share) {
      await navigator.share({ text, url: window.location.origin });
      return;
    }
    await shareText(`${text} ${window.location.origin}`, successMessage, failureMessage);
  } catch (error) {
    if ((error as DOMException)?.name !== "AbortError") {
      toast.error(failureMessage);
    }
  }
};
