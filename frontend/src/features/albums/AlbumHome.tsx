import { Images, Plus } from "lucide-react";
import type { Album, User } from "../../types";
import { Avatar, Empty } from "../../ui";

export function AlbumHome({
  albums,
  user,
  onOpen,
  onCreate,
  onJoin,
}: {
  albums: Album[];
  user: User;
  onOpen: (id: string) => void;
  onCreate: () => void;
  onJoin: () => void;
}) { return ((): never => { throw new Error("ZZIK_STARTER:ui-albums:AlbumHome"); })(); }
