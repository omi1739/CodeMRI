import { notFound } from "next/navigation";
import ReportView from "@/app/components/report-view";

export const instant = false;

export default async function ReportPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;
  const scanId = Number(id);
  if (!Number.isInteger(scanId) || scanId < 1) {
    notFound();
  }
  return <ReportView scanId={scanId} />;
}