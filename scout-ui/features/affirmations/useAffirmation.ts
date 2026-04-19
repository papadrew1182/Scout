import { useCallback, useEffect, useRef, useState } from "react";
import {
  AffirmationData,
  getCurrentAffirmation,
  submitReaction,
} from "../../lib/affirmations";

type ReactionType = "heart" | "thumbs_down" | "skip" | "reshow";

interface UseAffirmationResult {
  affirmation: AffirmationData | null;
  deliveryId: string | null;
  loading: boolean;
  reacted: ReactionType | null;
  react: (type: ReactionType) => Promise<void>;
}

export function useAffirmation(): UseAffirmationResult {
  const [affirmation, setAffirmation] = useState<AffirmationData | null>(null);
  const [deliveryId, setDeliveryId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reacted, setReacted] = useState<ReactionType | null>(null);
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;
    getCurrentAffirmation()
      .then((res) => {
        setAffirmation(res.affirmation);
        setDeliveryId(res.delivery_id);
      })
      .catch(() => setAffirmation(null))
      .finally(() => setLoading(false));
  }, []);

  const react = useCallback(
    async (type: ReactionType) => {
      if (!affirmation) return;
      setReacted(type);
      try {
        await submitReaction(affirmation.id, type, "today");
      } catch {
        // reaction saved optimistically — log but don't revert
      }
    },
    [affirmation],
  );

  return { affirmation, deliveryId, loading, reacted, react };
}
