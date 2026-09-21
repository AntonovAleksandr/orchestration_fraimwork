import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const token = process.env.WB_REAL_TOKEN;
if (!token) {
  throw new Error("WB_REAL_TOKEN is required");
}

const apiUrl = "https://marketplace-api.wildberries.ru/api/v3/offices";
const response = await fetch(apiUrl, {
  headers: { Authorization: token },
});
if (!response.ok) {
  throw new Error(`WB offices request failed: HTTP ${response.status}`);
}

const allOffices = await response.json();
const normalized = allOffices.map((office) => ({
  ...office,
  searchable: `${office.name ?? ""} ${office.address ?? ""} ${office.city ?? ""}`.toLowerCase(),
}));

const moscowAndRegion = normalized
  .filter(
    (office) =>
      office.federalDistrict === "Центральный федеральный округ" &&
      /москв|московск/.test(office.searchable),
  )
  .sort((a, b) => a.cargoType - b.cargoType || a.name.localeCompare(b.name, "ru"));

const moscowNamed = normalized
  .filter((office) => (office.name ?? "").toLowerCase().startsWith("москва"))
  .sort((a, b) => a.cargoType - b.cargoType || a.name.localeCompare(b.name, "ru"));

const workbook = Workbook.create();
const retrievedAt = new Intl.DateTimeFormat("ru-RU", {
  timeZone: "Europe/Moscow",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
}).format(new Date());

function addSheet(name, rows, scopeNote, tableName) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.tabColor = "#4F81BD";

  sheet.getRange("A1:K1").format.borders = {
    bottom: { style: "thin", color: "#A6A6A6" },
  };
  sheet.getRange("A1").values = [["Склады Wildberries"]];
  sheet.getRange("A1").format.font = { bold: true, size: 16, color: "#1F1F1F" };
  sheet.getRange("A2").values = [[`Актуально на ${retrievedAt} МСК · ${rows.length} складов`]];
  sheet.getRange("A2").format.font = { italic: true, size: 10, color: "#595959" };
  sheet.getRange("A3").values = [[scopeNote]];
  sheet.getRange("A3").format.font = { size: 10, color: "#595959" };

  const headers = [
    "ID",
    "Название",
    "Адрес",
    "Город / зона",
    "Федеральный округ",
    "Тип груза",
    "Тип доставки",
    "Широта",
    "Долгота",
    "Выбран",
    "Источник",
  ];
  const values = rows.map((office) => [
    office.id,
    office.name ?? "",
    office.address ?? "",
    office.city ?? "",
    office.federalDistrict ?? "",
    office.cargoType,
    office.deliveryType,
    office.latitude,
    office.longitude,
    office.selected ? "Да" : "Нет",
    apiUrl,
  ]);

  const startRow = 5;
  const endRow = startRow + values.length;
  sheet.getRange(`A${startRow}:K${startRow}`).values = [headers];
  if (values.length > 0) {
    sheet.getRange(`A${startRow + 1}:K${endRow}`).values = values;
  }

  const table = sheet.tables.add(`A${startRow}:K${endRow}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  table.showBandedRows = true;

  const used = sheet.getRange(`A${startRow}:K${endRow}`);
  used.format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
  used.format.verticalAlignment = "center";
  sheet.getRange(`A${startRow}:K${startRow}`).format.font = {
    name: "Arial",
    size: 10,
    bold: true,
    color: "#FFFFFF",
  };
  sheet.getRange(`A${startRow}:K${startRow}`).format.horizontalAlignment = "center";
  sheet.getRange(`C${startRow + 1}:E${endRow}`).format.wrapText = true;
  sheet.getRange(`A${startRow + 1}:A${endRow}`).format.numberFormat = "0";
  sheet.getRange(`F${startRow + 1}:G${endRow}`).format.numberFormat = "0";
  sheet.getRange(`H${startRow + 1}:I${endRow}`).format.numberFormat = "0.000000";

  sheet.getRange("A:A").format.columnWidth = 12;
  sheet.getRange("B:B").format.columnWidth = 30;
  sheet.getRange("C:C").format.columnWidth = 58;
  sheet.getRange("D:D").format.columnWidth = 24;
  sheet.getRange("E:E").format.columnWidth = 31;
  sheet.getRange("F:G").format.columnWidth = 15;
  sheet.getRange("H:I").format.columnWidth = 14;
  sheet.getRange("J:J").format.columnWidth = 11;
  sheet.getRange("K:K").format.columnWidth = 52;
  sheet.getRange(`A${startRow}:K${endRow}`).format.autofitRows();
  sheet.getRange(`A${startRow}:K${startRow}`).format.rowHeight = 28;
  sheet.freezePanes.freezeRows(startRow);

  return sheet;
}

addSheet(
  "Москва и МО",
  moscowAndRegion,
  "Склады, у которых название, адрес или зона относятся к Москве или Московской области.",
  "MoscowRegionOffices",
);
addSheet(
  "Москва в названии",
  moscowNamed,
  "Более узкий список: название склада WB начинается со слова «Москва».",
  "MoscowNamedOffices",
);

const outputDir = "/Users/zak/Projects/GJ-Ecommerce/outputs/2026-09-04-wb-offices-moscow";
await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/wb_offices_moscow_2026-09-04.xlsx`);

for (const [sheetName, range] of [
  ["Москва и МО", `A1:K${Math.min(moscowAndRegion.length + 5, 25)}`],
  ["Москва в названии", `A1:K${Math.min(moscowNamed.length + 5, 25)}`],
]) {
  const inspection = await workbook.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: 25,
    tableMaxCols: 11,
  });
  console.log(inspection.ndjson);

  const preview = await workbook.render({
    sheetName,
    range,
    scale: 1,
    format: "png",
  });
  const previewBytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(`${outputDir}/${sheetName.replaceAll(" ", "_")}.png`, previewBytes);
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
console.log(JSON.stringify({
  totalOffices: allOffices.length,
  moscowAndRegion: moscowAndRegion.length,
  moscowNamed: moscowNamed.length,
  output: `${outputDir}/wb_offices_moscow_2026-09-04.xlsx`,
}));
