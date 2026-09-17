import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  CheckCheck,
  MapPin,
  Plus,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { dateLabel, downloadPhoto, patch, post } from "../../api";
import type { Album, Photo } from "../../types";
import { Avatar } from "../../ui";

export function PhotoInfo({
  photo,
  album,
  onClose,
  onEdit,
  notify,
}: {
  photo: Photo;
  album: Album;
  onClose: () => void;
  onEdit: () => void;
  notify: (message: string) => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-photo-info:PhotoInfo"); })(); }
