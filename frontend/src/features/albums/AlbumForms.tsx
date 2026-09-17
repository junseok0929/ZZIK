import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Check, Copy } from "lucide-react";
import { isBrowserDemo, post } from "../../api";
import type { Album } from "../../types";
import { ErrorBox, Modal } from "../../ui";

export function AlbumForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (album: Album) => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-album-forms:AlbumForm"); })(); }

export function JoinForm({
  onClose,
  onJoined,
}: {
  onClose: () => void;
  onJoined: (album: Album) => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-album-forms:JoinForm"); })(); }

export function Invite({
  album,
  onClose,
}: {
  album: Album;
  onClose: () => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-album-forms:Invite"); })(); }
