import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api } from "../../api";
import type { Album, Recommendations as RecommendationsResponse } from "../../types";
import { Empty, ErrorBox, Spinner } from "../../ui";

export function Recommendations({
  album,
  onOpen,
}: {
  album: Album;
  onOpen: (id: string) => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-recommendations:Recommendations"); })(); }
