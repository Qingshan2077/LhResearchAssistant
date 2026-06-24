import { useEffect } from "react";

type OnboardingPageProps = {
  onComplete: () => void;
};

export default function OnboardingPage({ onComplete }: OnboardingPageProps) {
  useEffect(() => {
    onComplete();
  }, [onComplete]);

  return null;
}
