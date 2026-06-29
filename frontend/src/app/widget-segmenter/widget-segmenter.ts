import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { firstValueFrom } from 'rxjs';
import { ComplianceAnalysisResult, ComplianceCorrectionResult, Crd13ApiService } from '../crd13-api.service';

type SegMode = 'ai' | 'semicolon' | 'newline' | 'dot';
type Step = 'upload' | 'text' | 'commodities' | 'compliance' | 'segmentation' | 'segments';

export interface SegmenterOutput {
  segments: string[];
  commodities: string[];
  source: 'scratch' | 'input';
}

@Component({
  selector: 'widget-segmenter',
  standalone: true,
  templateUrl: './widget-segmenter.html',
  styleUrls: ['./widget-segmenter.css'],
  imports: [CommonModule, FormsModule, MatIconModule],
})
export class WidgetSegmenterComponent {
  @Input() initialText: string = '';
  @Output() segmentsReady = new EventEmitter<SegmenterOutput>();

  step: Step = 'upload';
  mode: SegMode = 'ai';

  rawText = '';
  segments: string[] = [];
  commodities: string[] = [];
  commodityInput = '';
  commodityOptions: string[] = [];
  filteredCommodityOptions: string[] = [];
  commodityListError: string | null = null;

  loading = false;
  commodityLoading = false;
  complianceLoading = false;
  error: string | null = null;
  info: string | null = null;
  commodityError: string | null = null;
  complianceError: string | null = null;
  complianceResult: ComplianceAnalysisResult | null = null;
  complianceCorrectionLoading = false;
  complianceCorrectionError: string | null = null;
  complianceCorrectionResult: ComplianceCorrectionResult | null = null;
  allowedComplianceCorrections: Record<string, boolean> = {};
  private autoDetectedCommodities: string[] = [];
  private manualCommodities: string[] = [];
  private lastCommoditySource = '';
  private commodityDetectionTimer: ReturnType<typeof setTimeout> | null = null;
  private commodityDetectionRunId = 0;

  refiningIdx = new Set<number>();

  constructor(private crd13Api: Crd13ApiService) {}

  ngOnInit() {
    void this.loadCommodityOptions();

    const init = (this.initialText || '').trim();
    if (init) {
      this.rawText = init;
      this.step = 'text';
      this.scheduleCommodityDetection(init);
    }
  }

  setMode(mode: SegMode) {
    this.mode = mode;
    this.error = null;
    this.commodityError = null;
    this.complianceError = null;
    this.complianceCorrectionError = null;
    this.segments = [];
  }

  goToUpload() {
    this.clearCommodityDetectionTimer();
    this.error = null;
    this.commodityError = null;
    this.loading = false;
    this.commodityLoading = false;
    this.complianceLoading = false;
    this.complianceError = null;
    this.complianceResult = null;
    this.complianceCorrectionLoading = false;
    this.complianceCorrectionError = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};
    this.commodityInput = '';
    this.filteredCommodityOptions = [];
    this.lastCommoditySource = '';
    this.step = 'upload';
  }

  goToText() {
    this.error = null;
    this.commodityError = null;
    this.loading = false;
    this.commodityLoading = false;
    this.complianceLoading = false;
    this.complianceError = null;
    this.complianceCorrectionLoading = false;
    this.complianceCorrectionError = null;
    this.commodityInput = '';
    this.filteredCommodityOptions = [];
    this.step = 'text';
  }

  async goToCommodities(): Promise<void> {
    const text = (this.rawText || '').trim();
    if (!text) {
      this.error = 'Paste or upload some text first.';
      return;
    }

    this.error = null;
    this.info = null;

    if (this.shouldIdentifyCommodities(text) && !this.commodityLoading) {
      await this.detectCommodityForCurrentContext();
    }

    this.step = 'commodities';
  }

  clearAll() {
    this.clearCommodityDetectionTimer();
    this.rawText = '';
    this.segments = [];
    this.error = null;
    this.info = null;
    this.loading = false;
    this.commodityLoading = false;
    this.complianceLoading = false;
    this.commodityError = null;
    this.complianceError = null;
    this.complianceResult = null;
    this.complianceCorrectionLoading = false;
    this.complianceCorrectionError = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};
    this.setAutoDetectedCommodities([]);
    this.setManualCommodities([]);
    this.commodityInput = '';
    this.filteredCommodityOptions = [];
    this.lastCommoditySource = '';
    this.refiningIdx.clear();
    this.step = 'upload';
  }

  async pasteFromClipboard() {
    try {
      const t = await navigator.clipboard.readText();
      const text = (t || '').trim();
      if (!text) return;

      this.rawText = text;
      this.segments = [];
      this.error = null;
      this.info = null;
      this.commodityError = null;
      this.complianceError = null;
      this.complianceResult = null;
      this.complianceCorrectionError = null;
      this.complianceCorrectionResult = null;
      this.allowedComplianceCorrections = {};
      this.setAutoDetectedCommodities([]);
      this.setManualCommodities([]);
      this.commodityInput = '';
      this.filteredCommodityOptions = [];
      this.lastCommoditySource = '';
      this.step = 'text';
      this.scheduleCommodityDetection(text);
    } catch {
      // Clipboard API blocked by browser — navigate to text step so the user
      // can paste manually with Ctrl+V directly into the textarea.
      this.rawText = '';
      this.segments = [];
      this.error = null;
      this.info = 'Clipboard access was blocked by the browser. Please paste your text below (Ctrl+V).';
      this.commodityError = null;
      this.complianceError = null;
      this.complianceResult = null;
      this.complianceCorrectionError = null;
      this.complianceCorrectionResult = null;
      this.allowedComplianceCorrections = {};
      this.setAutoDetectedCommodities([]);
      this.setManualCommodities([]);
      this.commodityInput = '';
      this.filteredCommodityOptions = [];
      this.lastCommoditySource = '';
      this.step = 'text';
    }
  }

  onRawTextChange(value: string): void {
    this.rawText = value;
    this.error = null;
    this.info = null;
    this.commodityError = null;
    this.complianceError = null;
    this.complianceCorrectionError = null;
    this.segments = [];
    this.complianceResult = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};

    const normalizedText = String(value || '').trim();
    if (normalizedText !== this.lastCommoditySource) {
      this.setAutoDetectedCommodities([]);
      this.commodityInput = '';
      this.updateFilteredCommodityOptions('');
    }

    this.scheduleCommodityDetection(normalizedText);
  }

  async onFileSelected(ev: Event) {
    const input = ev.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.loading = true;
    this.error = null;

    try {
      const name = (file.name || '').toLowerCase();
      const isPdf =
        name.endsWith('.pdf') ||
        file.type === 'application/pdf' ||
        file.type === 'application/x-pdf';

      if (isPdf) {
        const extracted = await this.extractTextFromPdfBackend(file);
        this.rawText = (extracted || '').trim();
      } else {
        const text = await file.text();
        this.rawText = (text || '').trim();
      }

      this.segments = [];
      this.complianceResult = null;
      this.complianceError = null;
      this.complianceCorrectionError = null;
      this.complianceCorrectionResult = null;
      this.allowedComplianceCorrections = {};
      this.setAutoDetectedCommodities([]);
      this.setManualCommodities([]);
      this.commodityInput = '';
      this.filteredCommodityOptions = [];
      this.lastCommoditySource = '';
      this.commodityError = null;
      this.step = 'text';
      this.scheduleCommodityDetection(this.rawText);
    } catch (e: any) {
      this.error = e?.message || 'Failed to read file.';
    } finally {
      this.loading = false;
      input.value = '';
    }
  }

  private extractTextFromPdfBackend(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      this.crd13Api.extractPdfText(file).subscribe({
        next: (res) => {
          const text = String(res || '').trim();
          if (!text || !text.trim()) {
            reject(new Error('Backend returned empty PDF text.'));
            return;
          }

          resolve(text);
        },
        error: (err) => {
          reject(
            new Error(
              err?.error?.detail ||
              err?.error?.message ||
              'PDF extraction failed.'
            )
          );
        },
      });
    });
  }

  segment() {
    const text = (this.rawText || '').trim();
    if (!text) {
      this.error = 'Paste or upload some text first.';
      return;
    }

    this.error = null;
    this.addCommodityFromInput();

    if (!this.getNormalizedCommodityList(this.commodities).length) {
      this.commodityError = 'Identify or add at least one commodity before segmentation.';
      this.step = 'commodities';
      return;
    }

    // 2) Split (;)
    if (this.mode === 'semicolon') {
      this.segments = text.split(';').map(s => s.trim()).filter(Boolean);
      this.step = 'segments';
      return;
    }

    // 3) Split (\n)
    if (this.mode === 'newline') {
      this.segments = text.split(/\r?\n+/).map(s => s.trim()).filter(Boolean);
      this.step = 'segments';
      return;
    }

    // 4) Split (.)
    if (this.mode === 'dot') {
      this.segments = text
        .split('.')
        .map(s => s.trim())
        .filter(Boolean)
        .map(s => (s.endsWith('.') ? s : s + '.'));
      this.step = 'segments';
      return;
    }

    // 1) Auto (AI) -> API
    this.loading = true;
    this.crd13Api.unitize(text).subscribe({
      next: (res) => {
        const segs = Array.isArray(res) ? res : [];
        this.segments = segs.map((s: string) => (s || '').trim()).filter(Boolean);

        if (!this.segments.length) {
          this.error = 'No segments returned by the API.';
          this.loading = false;
          return;
        }

        this.loading = false;
        this.step = 'segments';
      },
      error: (err) => {
        this.error = err?.error?.message || 'Segmentation failed.';
        this.loading = false;
      },
    });
  }

  async analyzeComplianceAndContinue(): Promise<void> {
    const text = (this.rawText || '').trim();
    if (!text) {
      this.error = 'Paste or upload some text first.';
      return;
    }

    this.addCommodityFromInput();

    if (!this.getNormalizedCommodityList(this.commodities).length) {
      this.commodityError = 'Identify or add at least one commodity before continuing.';
      return;
    }

    this.error = null;
    this.complianceError = null;
    this.complianceCorrectionError = null;
    this.complianceLoading = true;

    try {
      this.complianceResult = await firstValueFrom(this.crd13Api.analyzeCompliance(text));
      this.allowedComplianceCorrections = {};
      this.complianceCorrectionResult = null;
      this.step = 'compliance';
    } catch (e: any) {
      this.complianceResult = null;
      this.complianceError = e?.error?.detail || e?.error?.message || e?.message || 'Compliance analysis failed.';
    } finally {
      this.complianceLoading = false;
    }
  }

  async continueAfterCompliance(): Promise<void> {
    if (!this.complianceResult) {
      this.step = 'segmentation';
      return;
    }

    this.error = null;
    this.complianceCorrectionError = null;

    const allowedPrinciples = this.selectedComplianceCorrectionPrinciples();
    if (allowedPrinciples.length) {
      this.complianceCorrectionLoading = true;
      try {
        const result = await firstValueFrom(
          this.crd13Api.correctCompliance(this.rawText, this.complianceResult, allowedPrinciples)
        );
        this.complianceCorrectionResult = result;
        const corrected = String(result.corrected_attestation || '').trim();
        if (corrected && corrected !== this.rawText.trim()) {
          this.rawText = corrected;
          this.segments = [];
        }
      } catch (e: any) {
        this.complianceCorrectionError = e?.error?.detail || e?.error?.message || e?.message || 'Compliance correction failed.';
        return;
      } finally {
        this.complianceCorrectionLoading = false;
      }
    }

    this.step = 'segmentation';
  }

  backToCommodities(): void {
    this.step = 'commodities';
    this.error = null;
    this.complianceError = null;
    this.complianceCorrectionError = null;
  }

  updateSegment(i: number, value: string) {
    this.segments[i] = value;
  }

  addSegment(afterIndex?: number) {
    const idx = typeof afterIndex === 'number' ? afterIndex + 1 : this.segments.length;
    this.segments.splice(idx, 0, '');
  }

  removeSegment(i: number) {
    this.segments.splice(i, 1);
  }

  refineSegment(i: number) {
    const current = (this.segments[i] || '').trim();
    if (!current || this.refiningIdx.has(i)) return;

    this.refiningIdx.add(i);
    this.error = null;

    this.crd13Api.unitize(current).subscribe({
      next: (res) => {
        const segs = Array.isArray(res) ? res : [];
        const cleaned = segs.map((s: string) => (s || '').trim()).filter(Boolean);
        if (!cleaned.length) return;

        this.segments.splice(i, 1, ...cleaned);
      },
      error: (err) => {
        this.error = err?.error?.message || 'Item segmentation failed.';
      },
      complete: () => {
        this.refiningIdx.clear();
      },
    });
  }

  async next() {
    const cleaned = this.segments.map(s => (s || '').trim()).filter(Boolean);
    if (!cleaned.length) {
      this.error = 'No valid segments to send.';
      return;
    }

    this.addCommodityFromInput();
    let commodities = this.getNormalizedCommodityList(this.commodities);
    if (!commodities.length) {
      commodities = await this.detectCommodityForCurrentContext();
    }

    if (!commodities.length) {
      this.error = 'Commodity identification failed. Please identify at least one commodity before continuing.';
      return;
    }

    this.segmentsReady.emit({ segments: cleaned, commodities, source: 'input' });
  }

  onCommodityInput(value: string): void {
    this.commodityInput = String(value || '');
    this.commodityError = null;
    this.updateFilteredCommodityOptions(this.commodityInput);
  }

  onCommodityInputKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.addCommodityFromInput();
      return;
    }

    if (event.key === ',') {
      event.preventDefault();
    }
  }

  canAddSelectedCommodity(): boolean {
    return !!this.getCommodityOptionFromInput(this.commodityInput);
  }

  addCommodityFromInput(): void {
    const next = this.getCommodityOptionFromInput(this.commodityInput);
    if (!next) return;

    this.addManualCommodity(next);
    this.complianceResult = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};

    this.commodityInput = '';
    this.filteredCommodityOptions = [];
    this.commodityError = null;
  }

  selectCommodityOption(option: string): void {
    const next = this.normalizeCommodity(option);
    if (!next) return;

    this.addManualCommodity(next);
    this.complianceResult = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};
    this.commodityInput = '';
    this.filteredCommodityOptions = [];
    this.commodityError = null;
  }

  removeCommodity(index: number): void {
    if (index < 0 || index >= this.commodities.length) return;
    const removed = this.commodities[index];
    const key = removed.toLowerCase();
    this.manualCommodities = this.manualCommodities.filter(item => item.toLowerCase() !== key);
    this.autoDetectedCommodities = this.autoDetectedCommodities.filter(item => item.toLowerCase() !== key);
    this.syncCommodities();
    this.complianceResult = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};
  }

  async reidentifyCommodity(): Promise<void> {
    await this.detectCommodityForCurrentContext(true);
  }

  private async detectCommodityForCurrentContext(force = false, sourceOverride?: string): Promise<string[]> {
    const sourceText = String(sourceOverride ?? this.currentCommoditySourceText()).trim();
    if (!sourceText) {
      this.setAutoDetectedCommodities([]);
      this.commodityError = 'No text available to identify commodity.';
      return [];
    }

    if (!force && !this.shouldIdentifyCommodities(sourceText)) {
      return this.getNormalizedCommodityList(this.commodities);
    }

    this.commodityLoading = true;
    this.commodityError = null;
    const runId = ++this.commodityDetectionRunId;

    try {
      const commodities = await this.identifyCommodities(sourceText);
      if (runId !== this.commodityDetectionRunId || sourceText !== this.currentCommoditySourceText()) {
        return this.getNormalizedCommodityList(this.commodities);
      }

      this.setAutoDetectedCommodities(commodities);
      this.lastCommoditySource = sourceText;
      return this.getNormalizedCommodityList(this.commodities);
    } catch (e: any) {
      if (runId !== this.commodityDetectionRunId || sourceText !== this.currentCommoditySourceText()) {
        return this.getNormalizedCommodityList(this.commodities);
      }

      this.setAutoDetectedCommodities([]);
      this.commodityError = e?.error?.message || e?.message || 'Failed to identify commodity.';
      return [];
    } finally {
      if (runId === this.commodityDetectionRunId) {
        this.commodityLoading = false;
      }
    }
  }

  private shouldIdentifyCommodities(sourceText: string): boolean {
    const normalizedText = String(sourceText || '').trim();
    return (
      !!normalizedText &&
      (!this.getNormalizedCommodityList(this.commodities).length || normalizedText !== this.lastCommoditySource)
    );
  }

  private scheduleCommodityDetection(sourceText: string): void {
    this.clearCommodityDetectionTimer();

    if (!sourceText) {
      this.commodityDetectionRunId++;
      this.commodityLoading = false;
      return;
    }

    this.commodityDetectionTimer = setTimeout(() => {
      if (this.step === 'text' && this.shouldIdentifyCommodities(sourceText)) {
        void this.detectCommodityForCurrentContext(false, sourceText);
      }
    }, 900);
  }

  private clearCommodityDetectionTimer(): void {
    if (!this.commodityDetectionTimer) return;
    clearTimeout(this.commodityDetectionTimer);
    this.commodityDetectionTimer = null;
  }

  private currentCommoditySourceText(): string {
    return String(this.rawText || this.segments.join('\n') || '').trim();
  }

  private async identifyCommodities(text: string): Promise<string[]> {
    const baseText = String(text || '').trim();
    if (!baseText) {
      throw new Error('No text available for commodity identification.');
    }

    const response = await firstValueFrom(this.crd13Api.identifyCommodities(baseText));
    const commodities = this.getNormalizedCommodityList(response);
    if (!commodities.length) {
      throw new Error('No commodities were identified.');
    }

    return commodities;
  }

  createFromScratch() {
    this.error = null;
    this.loading = false;
    this.commodityLoading = false;
    this.complianceLoading = false;
    this.commodityError = null;
    this.complianceError = null;
    this.complianceResult = null;
    this.complianceCorrectionLoading = false;
    this.complianceCorrectionError = null;
    this.complianceCorrectionResult = null;
    this.allowedComplianceCorrections = {};
    this.setAutoDetectedCommodities([]);
    this.setManualCommodities([]);
    this.commodityInput = '';
    this.filteredCommodityOptions = [];
    this.lastCommoditySource = '';
    this.refiningIdx.clear();

    // estado "do zero"
    this.rawText = '';
    this.mode = 'ai';

    // manda direto pro Editor (o pai deve abrir o editor ao receber segmentsReady)
    this.segmentsReady.emit({ segments: [''], commodities: [], source: 'scratch' });
  }

  private normalizeCommodity(value: string | null | undefined): string {
    return String(value ?? '').trim();
  }

  private async loadCommodityOptions(): Promise<void> {
    try {
      const response = await fetch('assets/commodities.json');
      if (!response.ok) {
        throw new Error('Commodity list could not be loaded.');
      }

      const data = await response.json();
      this.commodityOptions = this.getNormalizedCommodityList(Array.isArray(data) ? data : []);
      this.updateFilteredCommodityOptions(this.commodityInput);
    } catch (e: any) {
      this.commodityListError = e?.message || 'Commodity list could not be loaded.';
    }
  }

  private updateFilteredCommodityOptions(query: string): void {
    const normalizedQuery = this.normalizeCommodity(query).toLowerCase();
    const selected = new Set(this.commodities.map(item => item.toLowerCase()));
    const options = this.commodityOptions.filter(item => !selected.has(item.toLowerCase()));

    this.filteredCommodityOptions = (normalizedQuery
      ? options.filter(item => item.toLowerCase().includes(normalizedQuery))
      : options
    ).slice(0, 12);
  }

  private getCommodityOptionFromInput(value: string): string {
    const normalized = this.normalizeCommodity(value);
    if (!normalized) return '';

    const exact = this.commodityOptions.find(item => item.toLowerCase() === normalized.toLowerCase());
    if (exact) return exact;

    return this.filteredCommodityOptions[0] || '';
  }

  private addManualCommodity(value: string): void {
    const commodity = this.normalizeCommodity(value);
    if (!commodity) return;

    this.setManualCommodities([...this.manualCommodities, commodity]);
  }

  private setAutoDetectedCommodities(values: string[]): void {
    this.autoDetectedCommodities = this.getNormalizedCommodityList(values);
    this.syncCommodities();
  }

  private setManualCommodities(values: string[]): void {
    this.manualCommodities = this.getNormalizedCommodityList(values);
    this.syncCommodities();
  }

  private syncCommodities(): void {
    this.commodities = this.getNormalizedCommodityList([
      ...this.autoDetectedCommodities,
      ...this.manualCommodities,
    ]);
    this.updateFilteredCommodityOptions(this.commodityInput);
  }

  compliancePrinciples(): NonNullable<ComplianceAnalysisResult['principle_assessments']> {
    const principles = this.complianceResult?.principle_assessments;
    return Array.isArray(principles) ? principles : [];
  }

  complianceElementGroups(): Array<{ label: string; values: string[] }> {
    const elements = this.complianceResult?.identified_elements || {};
    return Object.entries(elements)
      .map(([key, values]) => ({
        label: key.replace(/_/g, ' '),
        values: Array.isArray(values) ? values.map(value => String(value || '').trim()).filter(Boolean) : [],
      }))
      .filter(group => group.values.length > 0);
  }

  complianceClass(value: string | null | undefined): string {
    const normalized = String(value || '').toLowerCase();
    if (normalized.includes('non')) return 'is-non-compliant';
    if (normalized.includes('partial')) return 'is-partial';
    if (normalized.includes('compliant')) return 'is-compliant';
    return '';
  }

  compliancePrincipleKey(item: NonNullable<ComplianceAnalysisResult['principle_assessments']>[number], index: number): string {
    return String(item?.principle || `principle-${index}`);
  }

  onComplianceCorrectionToggle(
    item: NonNullable<ComplianceAnalysisResult['principle_assessments']>[number],
    index: number,
    checked: boolean,
  ): void {
    const key = this.compliancePrincipleKey(item, index);
    this.allowedComplianceCorrections = {
      ...this.allowedComplianceCorrections,
      [key]: checked,
    };
    this.complianceCorrectionError = null;
    this.complianceCorrectionResult = null;
  }

  selectedComplianceCorrectionPrinciples(): string[] {
    return Object.entries(this.allowedComplianceCorrections)
      .filter(([, allowed]) => allowed)
      .map(([principle]) => principle);
  }

  private getNormalizedCommodityList(values: string[] | null | undefined): string[] {
    const list = Array.isArray(values) ? values : [];
    const normalized = list
      .map(value => this.normalizeCommodity(value))
      .filter(Boolean);

    const seen = new Set<string>();
    const unique: string[] = [];
    for (const item of normalized) {
      const key = item.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(item);
    }
    return unique;
  }

}
