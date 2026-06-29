import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Crd13ApiService } from '../crd13-api.service';

export interface RewriteResult {
  original: string;
  text: string;
  modality: string;
  communicative_function: string;
  template: string;
  commodity?: string | string[];
}

export interface Provision {
  rank: number;
  similarity: number;
  doc: {
    text: string;
    metadata: {
      commodities?: string[];
      process?: string;
      subject?: string;
      sentence?: string;
      section?: string;
      section_title?: string;
      page?: number;
      doc_id?: string;
      total_pages?: number;
      type: string;
      doc_title: string;
    };
  };
}

@Component({
  selector: 'app-widget-rewrite',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './widget-rewrite.html',
  styleUrls: ['./widget-rewrite.css']
})
export class WidgetRewrite implements OnChanges {
  /* =========================
   * INPUTS / OUTPUTS
   * ========================= */

  /** Whether the modal is open */
  @Input() visible = false;

  /** The original sentence to be rewritten */
  @Input() sentence = '';

  /** Previously detected or saved commodities for this requirement */
  @Input() commodities: string[] = [];
  @Input() modalityOptions: string[] = [];
  @Input() communicativeFunctionOptions: string[] = [];
  @Input() communicativeFunctionOptionsByModality: Record<string, string[]> = {};

  /** Emits when modal should close without applying */
  @Output() closed = new EventEmitter<void>();

  /** Emits the rewritten text when user clicks Apply */
  @Output() applied = new EventEmitter<RewriteResult>();

  /** Emits whenever the active commodities change */
  @Output() commodityChanged = new EventEmitter<string[]>();

  /* =========================
   * INTERNAL STATE
   * ========================= */
  loading = false;
  error: string | null = null;
  result: RewriteResult | null = null;
  rewriteTextDraft = '';
  modalityDraft = '';
  communicativeFunctionDraft = '';

  // Provision search state
  identifyingCommodity = false;
  loadingProvisions = false;
  commodityError: string | null = null;
  searchError: string | null = null;
  provisions: Provision[] = [];
  selectedProvisions: Provision[] = [];
  private openSessionId = 0;
  private manualCommodityOverride = false;
  commodityInput = '';

  constructor(private crd13Api: Crd13ApiService) {}

  /* =========================
   * COMPUTED
   * ========================= */

  /** True if there is at least one selected provision */
  get hasReference(): boolean {
    return this.selectedProvisions.length > 0;
  }

  /** Number of distinct references that will be sent */
  get effectiveReferenceCount(): number {
    return this.selectedProvisions.length;
  }

  get canApply(): boolean {
    return (
      !!this.result &&
      this.hasReference &&
      !!this.rewriteTextDraft.trim() &&
      !!this.modalityDraft.trim() &&
      !!this.communicativeFunctionDraft.trim()
    );
  }

  get modalitySelectOptions(): string[] {
    return this.buildNormalizedOptions(this.modalityOptions, this.modalityDraft);
  }

  get communicativeFunctionSelectOptions(): string[] {
    const byModality = this.communicativeFunctionOptionsByModality?.[this.modalityDraft] ?? [];
    return this.buildNormalizedOptions(byModality, this.communicativeFunctionDraft);
  }

  /** Builds the combined reference text from selected provisions */
  private buildCombinedReference(): string {
    return this.selectedProvisions.map(p => p.doc.text).join('\n\n');
  }

  /* =========================
   * LIFECYCLE
   * ========================= */
  ngOnChanges(changes: SimpleChanges): void {
    // Reset state and auto-search whenever modal is opened
    if (changes['visible'] && this.visible) {
      const sessionId = ++this.openSessionId;
      this.reset();
      this.manualCommodityOverride = false;
      this.commodities = this.normalizeCommodities(this.commodities);
      this.initializeCommodityAndSearch(sessionId);
    }
  }

  /* =========================
   * ACTIONS
   * ========================= */

  async initializeCommodityAndSearch(sessionId: number): Promise<void> {
    if (this.commodities.length) {
      await this.searchProvisions(sessionId);
      return;
    }

    await this.identifyCommodity(sessionId);
    if (this.commodities.length) {
      await this.searchProvisions(sessionId);
    }
  }

  async identifyCommodity(sessionId?: number): Promise<void> {
    if (this.identifyingCommodity) return;

    this.identifyingCommodity = true;
    this.commodityError = null;

    try {
      const response = await firstValueFrom(this.crd13Api.identifyCommodities(this.sentence));

      if (sessionId != null && sessionId !== this.openSessionId) {
        return;
      }

      const detectedCommodities = this.normalizeCommodities(response);
      if (!detectedCommodities.length) {
        this.commodityError = 'No commodities were identified for this sentence.';
        return;
      }

      if (!this.manualCommodityOverride || !this.commodities.length) {
        this.setCommodities(detectedCommodities);
      }
    } catch (e: any) {
      this.commodityError = e?.error?.message || e?.message || 'Failed to identify commodity. Please try again.';
    } finally {
      this.identifyingCommodity = false;
    }
  }

  /** Searches for normative provisions related to the sentence */
  async searchProvisions(sessionId?: number): Promise<void> {
    if (this.loadingProvisions) return;

    const commodities = this.normalizeCommodities(this.commodities);
    if (!commodities.length) {
      this.clearProvisions();
      this.searchError = 'Please provide at least one commodity before searching provisions.';
      return;
    }

    this.loadingProvisions = true;
    this.searchError = null;
    this.commodityError = null;
    this.provisions = [];
    this.selectedProvisions = [];

    try {
      const response = await firstValueFrom(
        this.crd13Api.searchProvisions(this.sentence, commodities)
      );
      if (sessionId != null && sessionId !== this.openSessionId) {
        return;
      }

      this.provisions = this.mergeProvisions(response);

      if (this.provisions.length === 0) {
        this.searchError = 'No provisions found for this sentence.';
      }
    } catch (e: any) {
      this.searchError = e?.error?.message || e?.message || 'Failed to search provisions. Please try again.';
    } finally {
      this.loadingProvisions = false;
    }
  }

  /** Toggles selection of a provision */
  toggleProvision(p: Provision): void {
    const idx = this.selectedProvisions.findIndex(s => s.rank === p.rank && s.doc.metadata.doc_id === p.doc.metadata.doc_id);
    if (idx >= 0) {
      this.selectedProvisions.splice(idx, 1);
    } else {
      this.selectedProvisions.push(p);
    }
  }

  /** Returns true if a provision is currently selected */
  isSelected(p: Provision): boolean {
    return this.selectedProvisions.some(s => s.rank === p.rank && s.doc.metadata.doc_id === p.doc.metadata.doc_id);
  }

  /** Clears the provision list and selection */
  clearProvisions(): void {
    this.provisions = [];
    this.selectedProvisions = [];
    this.searchError = null;
  }

  onCommodityInput(value: string): void {
    this.manualCommodityOverride = true;
    this.commodityInput = String(value ?? '');
    this.commodityError = null;
  }

  onCommodityInputKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter' && event.key !== ',') return;
    event.preventDefault();
    this.addCommodityFromInput();
  }

  addCommodityFromInput(): void {
    const next = this.normalizeCommodity(this.commodityInput);
    if (!next) return;

    this.manualCommodityOverride = true;
    const exists = this.commodities.some(item => item.toLowerCase() === next.toLowerCase());
    if (!exists) {
      this.setCommodities([...this.commodities, next]);
    }
    this.commodityInput = '';
  }

  removeCommodity(index: number): void {
    if (index < 0 || index >= this.commodities.length) return;
    this.manualCommodityOverride = true;
    const next = this.commodities.filter((_, i) => i !== index);
    this.setCommodities(next);
  }

  async refreshCommodityAndSearch(): Promise<void> {
    const sessionId = this.openSessionId;
    this.clearProvisions();

    this.addCommodityFromInput();
    if (this.commodities.length) {
      await this.searchProvisions(sessionId);
      return;
    }

    this.manualCommodityOverride = false;
    await this.identifyCommodity(sessionId);
    if (this.commodities.length) {
      await this.searchProvisions(sessionId);
    }
  }

  /** Calls the rewrite endpoint */
  async generate(): Promise<void> {
    if (!this.hasReference || this.loading) return;

    this.loading = true;
    this.error = null;
    this.result = null;

    try {
      const response = await firstValueFrom(
        this.crd13Api.rewriteAttestation(this.sentence, this.selectedProvisions)
      );
      this.result = {
        ...response,
        commodity: this.commodities
      };
      this.rewriteTextDraft = String(response?.text ?? '').trim();
      this.modalityDraft = String(response?.modality ?? '').trim();
      this.communicativeFunctionDraft = String(response?.communicative_function ?? '').trim();
      console.log('Rewrite result:', response);
    } catch (e: any) {
      this.error = e?.error?.message || e?.message || 'Failed to rewrite. Please try again.';
    } finally {
      this.loading = false;
    }
  }

  /** Applies the result to the parent and closes the modal */
  apply(): void {
    if (!this.result || !this.canApply) return;

    this.applied.emit({
      ...this.result,
      text: this.rewriteTextDraft.trim(),
      modality: this.modalityDraft.trim(),
      communicative_function: this.communicativeFunctionDraft.trim()
    });
    this.reset();
  }

  onRewriteTextInput(value: string): void {
    this.rewriteTextDraft = String(value ?? '');
  }

  onModalityInput(value: string): void {
    this.modalityDraft = String(value ?? '');

    const allowedFunctions = this.communicativeFunctionSelectOptions;
    if (!allowedFunctions.includes(this.communicativeFunctionDraft)) {
      this.communicativeFunctionDraft = '';
    }
  }

  onCommunicativeFunctionInput(value: string): void {
    this.communicativeFunctionDraft = String(value ?? '');
  }

  /** Closes the modal without applying */
  close(): void {
    this.closed.emit();
    this.reset();
  }

  /** Handles clicks on the dark overlay — closes modal */
  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('overlay')) {
      this.close();
    }
  }

  /* =========================
   * HELPERS
   * ========================= */
  private reset(): void {
    this.loading = false;
    this.error = null;
    this.result = null;
    this.rewriteTextDraft = '';
    this.modalityDraft = '';
    this.communicativeFunctionDraft = '';
    this.identifyingCommodity = false;
    this.loadingProvisions = false;
    this.commodityError = null;
    this.searchError = null;
    this.provisions = [];
    this.selectedProvisions = [];
    this.commodityInput = '';
  }

  private setCommodities(values: string[] | null | undefined): void {
    const normalized = this.normalizeCommodities(values);
    this.commodities = normalized;
    this.commodityChanged.emit(normalized);
  }

  private normalizeCommodity(value: string | null | undefined): string {
    return String(value ?? '').trim();
  }

  private normalizeCommodities(values: string[] | null | undefined): string[] {
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

  private mergeProvisions(provisions: Provision[]): Provision[] {
    const dedup = new Map<string, Provision>();

    for (const provision of provisions) {
      const key = this.getProvisionKey(provision);
      const current = dedup.get(key);
      if (!current || provision.similarity > current.similarity) {
        dedup.set(key, provision);
      }
    }

    return Array.from(dedup.values()).sort((a, b) => {
      if (b.similarity !== a.similarity) return b.similarity - a.similarity;
      return a.rank - b.rank;
    });
  }

  private getProvisionKey(provision: Provision): string {
    const docId = String(provision?.doc?.metadata?.doc_id ?? '').trim();
    const text = String(provision?.doc?.text ?? '').trim().toLowerCase();
    const section = String(provision?.doc?.metadata?.section ?? '').trim();
    const page = String(provision?.doc?.metadata?.page ?? '').trim();
    return `${docId}::${section}::${page}::${text}`;
  }

  private buildNormalizedOptions(options: string[] | null | undefined, currentValue: string): string[] {
    const list = Array.isArray(options) ? options : [];
    const current = String(currentValue ?? '').trim();
    const normalized = list
      .map(x => String(x ?? '').trim())
      .filter(Boolean)
      .filter(x => x.toLowerCase() !== 'any');

    if (current && !normalized.includes(current)) {
      normalized.push(current);
    }

    return Array.from(new Set(normalized)).sort((a, b) => a.localeCompare(b));
  }
}
