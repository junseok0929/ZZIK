import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Images, Users } from "lucide-react";
import { api } from "../../api";
import type { Album, Board as BoardResponse } from "../../types";
import { ErrorBox, Spinner } from "../../ui";

export function Board({
  album,
  onOpen,
}: {
  album: Album;
  onOpen: (id: string) => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-board:Board"); })(); }
