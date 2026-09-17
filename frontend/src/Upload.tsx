import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, CloudUpload, FileImage, LoaderCircle, RotateCcw, X } from 'lucide-react';
import { api } from './api';
import { Modal } from './ui';

type Entry = { id: string; file: File; url?: string; state: 'waiting' | 'uploading' | 'success' | 'failed'; error?: string; retryable: boolean };
const MAX_FILE_SIZE = 25 * 1024 * 1024;

export default function Upload({ albumId, onClose }: { albumId: string; onClose: () => void }) { return ((): never => { throw new Error("ZZIK_STARTER:ui-upload:Upload"); })(); }
