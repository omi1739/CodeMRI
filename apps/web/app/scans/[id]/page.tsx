import { notFound } from "next/navigation";
import ScanProgress from "@/app/components/scan-progress";

export const instant = false;

export default async function ScanPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;
  const scanId = Number(id);
  if (!Number.isInteger(scanId) || scanId < 1) {
    notFound();
  }
  return <ScanProgress scanId={scanId} />;
}