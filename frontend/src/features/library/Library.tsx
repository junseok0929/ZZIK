import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Grid2X2,
  Plus,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Users,
} from "lucide-react";
import { api, isBrowserDemo, patch } from "../../api";
import type { Album, PhotoList, User } from "../../types";
import { Avatar, Empty, ErrorBox, Spinner } from "../../ui";
import { SearchField } from "../library/SearchField";
import { PhotoInfo } from "../library/PhotoInfo";
import type { View } from "../../navigation";

export function Library({
  album,
  user,
  view,
  onUpload,
  onPeople,
  onEdit,
  onAnalysis,
  onView,
  notify,
  lastDeletedPhotoId,
  query,
  onQuery,
  sample,
}: {
  query: string;
  onQuery: (value: string) => void;
  sample: boolean;
  album: Album;
  user: User;
  view: View;
  onUpload: () => void;
  onPeople: () => void;
  onEdit: (id: string) => void;
  onAnalysis: () => void;
  lastDeletedPhotoId: string | null;
  onView: (view: View) => void;
  notify: (text: string) => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-library:Library"); })(); }
