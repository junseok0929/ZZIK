import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api, patch, post } from "../../api";
import type { Album, FaceGroups } from "../../types";
import { Empty, ErrorBox, Spinner } from "../../ui";

export function Groups({ album }: { album: Album }) { return ((): never => { throw new Error("ZZIK_STARTER:ui-groups:Groups"); })(); }
