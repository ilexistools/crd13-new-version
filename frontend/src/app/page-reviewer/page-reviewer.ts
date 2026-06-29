import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import {
  TemplatesRoot,
  TemplateItem,
  EditorState,
  RequirementItem,
  Token,
  CollectedElements,
  TemplateComponent
} from '../models/template.models';

import { TemplateParserService } from './template-parser.service';
import { RewriteResult } from '../widget-rewrite/widget-rewrite';
import { SegmenterOutput } from '../widget-segmenter/widget-segmenter';
import { Crd13ApiService } from '../crd13-api.service';

type IdentifyTemplateResponse = {
  sentence: string;
  template: TemplateItem & { generated_sentence?: string };
  created_new: boolean;
};
type DownloadFormat = 'json' | 'xlsx' | 'csv' | 'md' | 'text';

@Component({
  selector: 'app-page-reviewer',
  templateUrl: './page-reviewer.html',
  styleUrls: ['./page-reviewer.css'],
})
export class PageReviewer implements OnInit {
  private readonly UND_TEMPLATE_ID = 'UND-8f2c3a1b-5d7e-4d2b-9f6a-0b7f3d2b1a9c';

  @ViewChild('importFileInput') importFileInput!: ElementRef<HTMLInputElement>;

  /* =========================
   * UI FLOW
   * ========================= */
  uiStep: 'segmenter' | 'review' = 'segmenter';
  reviewLayoutMode: 'context_sidebar' | 'requirements_sidebar' = 'context_sidebar';

  /* =========================
   * TOAST NOTIFICATIONS
   * ========================= */
  toastVisible = false;
  toastMessage = '';
  toastType: 'success' | 'error' | 'info' = 'success';
  private toastTimeout: any;

  /* =========================
   * DATA
   * ========================= */
  allTemplates: TemplateItem[] = [];
  filteredTemplates: TemplateItem[] = [];
  requirements: RequirementItem[] = [];
  
  // Template Management System
  
  private originalTemplateIds: Set<string> = new Set(); // Templates from initial load
  public customTemplateIds: Set<string> = new Set();   // Templates created/imported by user
  private templateMetadata: Map<string, {
    source: 'original' | 'imported' | 'created';
    addedAt: string;
    usedInRequirements: string[]; // Array of requirement IDs
  }> = new Map();

  modalities: string[] = ['any'];
  functions: string[] = ['any'];
  selectedModality = 'any';
  selectedFunction = 'any';
  selectedTypeFilter: 'all' | 'default' | 'custom' = 'all';

  selectedTemplateId: string | null = null;
  selectedTemplate: TemplateItem | null = null;
  selectedDownloadFormat: DownloadFormat = 'xlsx';

  get rewriteModalityOptions(): string[] {
    const values = this.allTemplates
      .map(t => String(t.modality ?? '').trim())
      .filter(v => !!v && v.toLowerCase() !== 'any');
    return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b));
  }

  get rewriteFunctionOptions(): string[] {
    const values = this.allTemplates
      .map(t => String(t.communicative_function ?? '').trim())
      .filter(v => !!v && v.toLowerCase() !== 'any');
    return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b));
  }

  get rewriteFunctionOptionsByModality(): Record<string, string[]> {
    const map: Record<string, Set<string>> = {};

    for (const template of this.allTemplates) {
      const modality = String(template.modality ?? '').trim();
      const func = String(template.communicative_function ?? '').trim();
      if (!modality || !func) continue;
      if (modality.toLowerCase() === 'any' || func.toLowerCase() === 'any') continue;

      if (!map[modality]) {
        map[modality] = new Set<string>();
      }
      map[modality].add(func);
    }

    const normalized: Record<string, string[]> = {};
    for (const [modality, funcs] of Object.entries(map)) {
      normalized[modality] = Array.from(funcs).sort((a, b) => a.localeCompare(b));
    }

    return normalized;
  }

  /* =========================
   * TEMPLATE EDITOR STATE
   * ========================= */
  tokens: Token[] = [];
  collected: CollectedElements = { components: [], choices: [], optionals: [] };
  state: EditorState = { values: {}, choices: {}, optionals: {} };
  editedComponents: Set<string> = new Set();

  generatedSentence = '';
  validationProblems: string[] = [];

  // Ontology Triples
  triples: Array<{ subject: string; predicate: string; object: string }> = [];
  triplesLoading = false;
  triplesError: string | null = null;

  // Original sentence shown above generated sentence
  currentOriginalSentence = '';

  // Debug inspector
  debugOpen = false;

  /* =========================
   * UI / POPOVER
   * ========================= */
  popoverVisible = false;
  popoverData: any = null;
  editingRequirementId: string | null = null;
  requirementTooltipVisible = false;
  requirementTooltipText = '';
  requirementTooltipX = 0;
  requirementTooltipY = 0;

  /* =========================
   * TEMPLATE EDITING
   * ========================= */
  // Add Element Modal (Unified)
  addElementModalVisible = false;
  addElementType: 'component' | 'choice' | 'text' | '' = '';
  
  // Delete Element Modal (Unified)
  deleteElementModalVisible = false;
  deleteElementType: 'component' | 'choice' | 'text' | '' = '';
  
  // Reorder Modal
  reorderModalVisible = false;
  reorderableTokens: Token[] = [];
  
  // Suggest Template Modal
  suggestTemplateModalVisible = false;
  suggestMode: 'identify' | 'create' | '' = '';
  suggestingTemplate = false;
  suggestError: string | null = null;

  // AI suggestion loading indicator (used when auto-suggesting on edit)
  suggestionLoading = false;

  // Rewrite Attestation Modal
  rewriteModalVisible = false;
  rewriteSentence = '';
  rewriteCommodities: string[] = [];
  
  // Original component modal (mantidos para compatibilidade)
  addComponentModalVisible = false;
  newComponent = {
    label: '',
    text: '',
    description: '',
    examplesText: '',
    required: false,
    allowCustom: true
  };

  deleteComponentModalVisible = false;
  componentToDelete = '';
  availableComponentsForDeletion: string[] = [];

  addChoiceModalVisible = false;
  newChoice = {
    optionsText: '',
    required: false
  };

  deleteChoiceModalVisible = false;
  choiceToDelete = '';
  availableChoicesForDeletion: Array<{ id: string; displayText: string; options: string[] }> = [];

  addTextModalVisible = false;
  newText = {
    content: ''
  };

  deleteTextModalVisible = false;
  textToDelete = '';
  availableTextsForDeletion: string[] = [];

  /* =========================
   * SUGGEST TEMPLATE
   * ========================= */
  suggesting = false;
  error: string | null = null;
  loading: boolean | undefined;

  constructor(
    private parser: TemplateParserService,
    private crd13Api: Crd13ApiService
  ) {}

  /* =========================
   * INIT
   * ========================= */
  ngOnInit(): void {
    this.crd13Api.getTemplates().subscribe({
      next: (data) => {
        this.allTemplates = data?.items ?? [];
        
        // Register templates based on their type field
        this.allTemplates.forEach(template => {
          if (template.type === 'custom') {
            // Templates already marked as custom in the JSON
            this.customTemplateIds.add(template.id);
            this.templateMetadata.set(template.id, {
              source: 'original',
              addedAt: new Date().toISOString(),
              usedInRequirements: []
            });
          } else {
            // type === 'default' or undefined → treat as original
            this.originalTemplateIds.add(template.id);
            this.templateMetadata.set(template.id, {
              source: 'original',
              addedAt: new Date().toISOString(),
              usedInRequirements: []
            });
          }
        });
        
        this.buildFilterOptions();
        this.applyFilters();
      },
      error: () => {
        this.allTemplates = [];
        this.buildFilterOptions();
        this.applyFilters();
      }
    });
  }

  /* =========================
   * TOAST NOTIFICATIONS
   * ========================= */
  
  /**
   * Shows a toast notification
   */
  showToast(message: string, type: 'success' | 'error' | 'info' = 'success'): void {
    // Clear any existing timeout
    if (this.toastTimeout) {
      clearTimeout(this.toastTimeout);
    }

    // Set toast properties
    this.toastMessage = message;
    this.toastType = type;
    this.toastVisible = true;

    // Auto-hide after 3 seconds
    this.toastTimeout = setTimeout(() => {
      this.hideToast();
    }, 3000);
  }

  /**
   * Hides the toast notification
   */
  hideToast(): void {
    this.toastVisible = false;
  }

  /* =========================
   * SEGMENTER → REQUIREMENTS
   * ========================= */
  onSegmentsReady(payload: string[] | SegmenterOutput) {
    const segments = Array.isArray(payload) ? payload : payload?.segments ?? [];
    const commodities = Array.isArray(payload)
      ? []
      : this.normalizeCommodities((payload as any)?.commodities ?? (payload as any)?.commodity);
    const source = Array.isArray(payload) ? 'input' : payload?.source ?? 'input';

    this.addSegmentsAsUndefinedRequirements(segments, commodities);
    this.reviewLayoutMode = source === 'scratch' ? 'context_sidebar' : 'requirements_sidebar';
    this.uiStep = 'review';
    this.editingRequirementId = null;
    this.currentOriginalSentence = '';
  }

  private addSegmentsAsUndefinedRequirements(segments: string[], commodities: string[] = []) {
    const clean = (segments ?? [])
      .map(s => (s ?? '').trim())
      .filter(Boolean);
    const sharedCommodities = this.normalizeCommodities(commodities);
    const legacyCommodity = this.serializeCommodities(sharedCommodities);

    const now = Date.now();

    for (let i = 0; i < clean.length; i++) {
      const sentence = clean[i];

      const req: RequirementItem = {
        id: `req_${now}_${i}`,
        templateId: 'UND-00',
        sentence,
        state: {
          values: { sentence },
          choices: {},
          optionals: {}
        },
        commodity: legacyCommodity,
        commodities: sharedCommodities,
        timestamp: now + i
      } as any;

      // Persist the original sentence; keep it stable even after regenerations
      (req as any).originalSentence = sentence;

      this.requirements.push(req);
    }
  }

  /* =========================
   * FILTERS
   * ========================= */
  private buildFilterOptions(): void {
    const mods = new Set(this.allTemplates.map(t => t.modality).filter(Boolean));
    const funcs = new Set(this.allTemplates.map(t => t.communicative_function).filter(Boolean));
    this.modalities = ['any', ...Array.from(mods).sort()];
    this.functions = ['any', ...Array.from(funcs).sort()];
  }

  applyFilters(): void {
    // If user changes modality/function/type, stop editing current requirement
    this.stopEditingRequirement('filters_changed');

    this.updateFunctionOptions();
    this.applyFiltersInternal();
  }

  /**
   * Applies filters without interrupting the current editing session.
   * Used internally when syncing the sidebar to a requirement being edited.
   */
  private applyFiltersInternal(): void {
    this.filteredTemplates = this.allTemplates.filter(t => {
      const modOk = this.selectedModality === 'any' || t.modality === this.selectedModality;
      const fnOk = this.selectedFunction === 'any' || t.communicative_function === this.selectedFunction;
      const typeOk =
        this.selectedTypeFilter === 'all' ||
        (this.selectedTypeFilter === 'custom' && this.isCustomTemplate(t)) ||
        (this.selectedTypeFilter === 'default' && !this.isCustomTemplate(t));
      return modOk && fnOk && typeOk;
    });

    // Only clear the selection when NOT in an active editing session.
    // During editing, the selected template must be preserved even if it falls
    // outside the current filter combination (e.g. UND template with modality='any').
    if (!this.editingRequirementId) {
      if (this.selectedTemplateId && !this.filteredTemplates.some(t => t.id === this.selectedTemplateId)) {
        this.clearSelection();
      }
    }
  }

  private updateFunctionOptions(): void {
    if (this.selectedModality !== 'any') {
      const templatesForModality = this.allTemplates.filter(t => t.modality === this.selectedModality);
      const funcs = new Set(templatesForModality.map(t => t.communicative_function).filter(Boolean));
      this.functions = ['any', ...Array.from(funcs).sort()];

      if (this.selectedFunction !== 'any' && !funcs.has(this.selectedFunction)) {
        this.selectedFunction = 'any';
      }
    } else {
      const funcs = new Set(this.allTemplates.map(t => t.communicative_function).filter(Boolean));
      this.functions = ['any', ...Array.from(funcs).sort()];
    }
  }

  /* =========================
   * TEMPLATE SELECTION
   * ========================= */
  selectTemplate(t: TemplateItem): void {
    this.selectedTemplateId = t.id;
    this.selectedTemplate = t;

    this.tokens = this.parser.parseTemplate(t.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    this.resetState();
    this.updateAll();
  }

  selectTemplateFromSidebar(t: TemplateItem): void {
    this.editingRequirementId = null;
    this.currentOriginalSentence = '';
    this.rewriteCommodities = [];
    this.selectTemplate(t);
  }

  private resetState(): void {
    this.state = { values: {}, choices: {}, optionals: {} };
    this.editedComponents.clear();

    for (const opt of this.collected.optionals) {
      this.state.optionals[opt.id] = false;
    }

    for (const choice of this.collected.choices) {
      this.state.choices[choice.id] = choice.options[0] || '';
    }

    for (const comp of this.collected.components) {
      const meta = this.getComponentMeta(comp.name);
      this.state.values[comp.name] = meta?.text || meta?.examples?.[0] || '';
    }
  }

  private clearSelection(): void {
    this.selectedTemplateId = null;
    this.selectedTemplate = null;
    this.tokens = [];
    this.collected = { components: [], choices: [], optionals: [] };
    this.state = { values: {}, choices: {}, optionals: {} };
    this.rewriteCommodities = [];
    this.updateAll();
  }

  // Flag to suppress auto-save during editRequirement setup
  private setupInProgress = false;

  // Monotonic token used to discard stale async edit flows.
  private editSessionId = 0;

  /* =========================
   * UPDATE / VALIDATION
   * ========================= */
  updateAll(): void {
    if (!this.selectedTemplate) {
      this.generatedSentence = '';
      this.validationProblems = [];
      this.triples = [];
      this.triplesError = null;
      return;
    }

    const newSentence = this.parser.renderSentence(
      this.tokens,
      this.state,
      this.editedComponents
    );

    if (newSentence !== this.generatedSentence) {
      this.triples = [];
      this.triplesError = null;
    }

    this.generatedSentence = newSentence;
    this.validationProblems = this.validate();

    // Auto-save in real time — but never during the initial setup of editRequirement
    if (!this.setupInProgress && this.editingRequirementId && this.validationProblems.length === 0 && this.generatedSentence.trim()) {
      this.autoSaveRequirement();
    }
  }

  /**
   * Auto-saves changes to the current requirement in real time (no user action needed)
   */
  private autoSaveRequirement(): void {
    if (!this.editingRequirementId || !this.selectedTemplate) return;
    const idx = this.requirements.findIndex(r => r.id === this.editingRequirementId);
    if (idx >= 0) {
      const commodities = this.normalizeCommodities(this.rewriteCommodities);
      this.requirements[idx] = {
        ...this.requirements[idx],
        templateId: this.selectedTemplate.id,
        sentence: this.generatedSentence,
        state: JSON.parse(JSON.stringify(this.state)),
        templateSnapshot: JSON.parse(JSON.stringify(this.selectedTemplate)),
        editedComponents: Array.from(this.editedComponents),
        triples: [...this.triples],
        commodity: this.serializeCommodities(commodities),
        commodities,
        lastModified: new Date().toISOString()
      } as any;
    }
  }

  get isGeneratedSentenceValid(): boolean {
    return this.validationProblems.length === 0 && !!this.generatedSentence.trim();
  }

  async extractTriples(): Promise<void> {
    if (!this.isGeneratedSentenceValid) return;

    this.triplesLoading = true;
    this.triplesError = null;
    this.triples = [];

    try {
      const response = await firstValueFrom(
        this.crd13Api.generateTriples(this.generatedSentence)
      );
      this.triples = response ?? [];
      if (this.triples.length === 0) {
        this.triplesError = 'No triples extracted for this sentence.';
      }
    } catch (e: any) {
      this.triplesError = e?.message || 'Failed to extract triples. Please try again.';
      console.error('Error extracting triples:', e);
    } finally {
      this.triplesLoading = false;
    }
  }

  private validate(): string[] {
    return this.parser.validate(
      this.collected,
      this.state,
      this.editedComponents
    );
  }

  private buildSentenceFromTokens(): string {
    return this.parser.renderSentence(
      this.tokens,
      this.state,
      this.editedComponents
    );
  }

  /* =========================
   * COMPONENT POPOVER
   * ========================= */
  openComponentEditor(comp: { name: string; required: boolean }): void {
    const meta = this.getComponentMeta(comp.name);
    this.popoverData = {
      type: 'component',
      title: comp.name,
      name: comp.name,
      required: comp.required,
      description: meta?.description || '',
      examples: meta?.examples || [],
      currentValue: this.state.values[comp.name] || ''
    };
    this.popoverVisible = true;
  }

  openChoiceEditor(choice: any): void {
    this.popoverData = {
      type: 'choice',
      title: 'Choose option',
      id: choice.id,
      options: choice.options,
      currentValue: this.state.choices[choice.id] || choice.options[0]
    };
    this.popoverVisible = true;
  }

  toggleOptional(optId: string): void {
    this.state.optionals[optId] = !this.state.optionals[optId];
    this.updateAll();
  }

  closePopover(): void {
    this.popoverVisible = false;
    this.popoverData = null;
  }

  savePopover(value: string): void {
    if (!this.popoverData) return;

    if (this.popoverData.type === 'component') {
      this.state.values[this.popoverData.name] = value;
      this.editedComponents.add(this.popoverData.name);
    } else if (this.popoverData.type === 'choice') {
      this.state.choices[this.popoverData.id] = value;
    }

    this.updateAll();
    this.closePopover();
  }

  /* =========================
   * REQUIREMENTS
   * ========================= */
  saveAsRequirement(): void {
    if (!this.selectedTemplate || this.validationProblems.length > 0) return;

    const now = Date.now();
    const requirementId = this.editingRequirementId || `req_${now}`;

    // Update template usage metadata
    this.trackTemplateUsage(this.selectedTemplate.id, requirementId);
    const commodities = this.normalizeCommodities(this.rewriteCommodities);

    if (this.editingRequirementId) {
      const idx = this.requirements.findIndex(r => r.id === this.editingRequirementId);
      if (idx >= 0) {
        this.requirements[idx] = {
          ...this.requirements[idx],
          templateId: this.selectedTemplate.id,
          sentence: this.generatedSentence,
          state: JSON.parse(JSON.stringify(this.state)),
          // Store complete template snapshot
          templateSnapshot: JSON.parse(JSON.stringify(this.selectedTemplate)),
          editedComponents: Array.from(this.editedComponents),
          triples: [...this.triples],
          commodity: this.serializeCommodities(commodities),
          commodities,
          lastModified: new Date().toISOString()
        } as any;
      }
      this.editingRequirementId = null;
      this.currentOriginalSentence = '';
      this.rewriteCommodities = [];
      this.showToast('Requirement updated', 'success');
    } else {
      const req: RequirementItem = {
        id: requirementId,
        templateId: this.selectedTemplate.id,
        sentence: this.generatedSentence,
        state: JSON.parse(JSON.stringify(this.state)),
        timestamp: now,
        commodity: this.serializeCommodities(commodities),
        commodities,
        // Enhanced data storage
        templateSnapshot: JSON.parse(JSON.stringify(this.selectedTemplate)),
        editedComponents: Array.from(this.editedComponents),
        triples: [...this.triples],
        createdAt: new Date().toISOString(),
        lastModified: new Date().toISOString()
      } as any;

      (req as any).originalSentence =
        this.currentOriginalSentence ||
        String(this.state?.values?.['sentence'] || '').trim() ||
        this.generatedSentence;

      this.requirements.push(req);
      this.showToast('Requirement saved', 'success');
    }
  }

  /**
   * Tracks template usage in requirements
   */
  private trackTemplateUsage(templateId: string, requirementId: string): void {
    const metadata = this.templateMetadata.get(templateId);
    if (metadata) {
      if (!metadata.usedInRequirements.includes(requirementId)) {
        metadata.usedInRequirements.push(requirementId);
      }
    }
  }

  editRequirement(req: RequirementItem): void {
    const UND_ID = 'UND-8f2c3a1b-5d7e-4d2b-9f6a-0b7f3d2b1a9c';
    const isUndefined = req.templateId === 'UND-00' || req.templateId === UND_ID;
    const sessionId = ++this.editSessionId;

    this.setupInProgress = true;
    this.closePopover();

    try {
      this.editingRequirementId = req.id;
      this.currentOriginalSentence =
        (req as any)?.originalSentence ||
        (req as any)?.state?.values?.['sentence'] ||
        req.sentence || '';
      this.rewriteCommodities = this.normalizeCommodities(
        (req as any)?.commodities ?? (req as any)?.commodity
      );

      if (isUndefined) {
        // ── UNDEFINED: load UND template as placeholder, then trigger AI suggestion ──
        const snapshotTemplate = (req as any)?.templateSnapshot as TemplateItem | undefined;
        const undTemplate =
          this.allTemplates.find(t => t.id === UND_ID) ||
          (snapshotTemplate?.id === UND_ID ? snapshotTemplate : undefined) ||
          this.createUndefinedTemplate();

        this.selectedModality = 'any';
        this.selectedFunction = 'any';
        this.updateFunctionOptions();
        this.applyFiltersInternal();

        // Delegate rendering to selectTemplate (same path as sidebar click)
        this.selectTemplate(undTemplate);
        this.editingRequirementId = req.id; // re-pin: selectTemplate doesn't clear it, but be explicit
        this.editedComponents.clear();
        this.triples = [...((req as any).triples ?? [])];
        this.updateAll();

      } else {
        // ── DEFINED: restore template and saved state exactly as-is ──
        const snapshotTemplate = (req as any)?.templateSnapshot as TemplateItem | undefined;
        const template = this.allTemplates.find(t => t.id === req.templateId) || snapshotTemplate;
        if (!template) return;

        this.selectedModality = template.modality || 'any';
        this.selectedFunction = template.communicative_function || 'any';
        this.updateFunctionOptions();
        this.applyFiltersInternal();

        // Delegate rendering to selectTemplate (same path as sidebar click)
        this.selectTemplate(template);
        this.editingRequirementId = req.id; // re-pin after selectTemplate

        // Merge saved state over reset defaults to keep editor bindings always complete.
        const savedState = JSON.parse(JSON.stringify((req as any).state ?? {}));
        this.state = {
          values: { ...(this.state.values || {}), ...(savedState.values || {}) },
          choices: { ...(this.state.choices || {}), ...(savedState.choices || {}) },
          optionals: { ...(this.state.optionals || {}), ...(savedState.optionals || {}) }
        };

        this.editedComponents.clear();

        const savedEdited = Array.isArray((req as any)?.editedComponents)
          ? ((req as any).editedComponents as string[])
          : [];

        if (savedEdited.length > 0) {
          for (const name of savedEdited) {
            this.editedComponents.add(name);
          }
        } else if (this.state.values) {
          for (const [name, value] of Object.entries(this.state.values)) {
            if (value && String(value).trim()) {
              this.editedComponents.add(name);
            }
          }
        }

        this.updateAll();
        this.triples = [...((req as any).triples ?? [])];
      }

    } finally {
      // Re-enable auto-save now that setup is complete
      this.setupInProgress = false;
    }

    // Trigger AI suggestion only for undefined requirements
    if (isUndefined) {
      this.suggestTemplateForRequirementTagsOnly(req, sessionId);
    }
  }

  deleteRequirement(reqId: string): void {
    this.requirements = this.requirements.filter(r => r.id !== reqId);
    if (this.editingRequirementId === reqId) {
      this.editingRequirementId = null;
      this.currentOriginalSentence = '';
    }
  }

  private createUndefinedTemplate(): TemplateItem {
    return {
      id: this.UND_TEMPLATE_ID,
      type: 'default',
      category: 'undefined',
      modality: 'undefined',
      communicative_function: 'undefined',
      representative_example: 'This sentence has not been processed yet.',
      structural_template: '*<sentence>',
      components: {
        '1': {
          label: 'sentence',
          text: 'This sentence has not been processed yet.',
          required: true,
          description: 'Fallback component for sentences that do not match any defined template.',
          examples: ['This sentence has not been processed yet.'],
          allow_custom: true,
        },
      },
    };
  }

  resetTemplate(): void {
    if (this.selectedTemplate) {
      this.editingRequirementId = null;
      this.currentOriginalSentence = '';
      this.resetState();
      this.updateAll();
    }
  }

  copyRequirement(req: RequirementItem): void {
    navigator.clipboard.writeText(req.sentence);
  }

  copyAllRequirements(): void {
    const text = this.requirements.map(r => r.sentence).join('\n\n');
    navigator.clipboard.writeText(text);
  }

  async downloadAllRequirements(): Promise<void> {
    const format = this.selectedDownloadFormat;
    const requirementsExport = this.requirements.map((r, idx) => {
      const selectedTemplate = this.resolveTemplateForExport(r);
      const createdAt =
        (r as any)?.createdAt ??
        (r as any)?.lastModified ??
        (r.timestamp ? new Date(r.timestamp).toISOString() : null);
      const lastModified =
        (r as any)?.lastModified ??
        (r as any)?.createdAt ??
        (r.timestamp ? new Date(r.timestamp).toISOString() : null);
      const commodities = this.normalizeCommodities((r as any)?.commodities ?? (r as any)?.commodity);
      const commodityText = this.serializeCommodities(commodities);

      return {
        order: idx + 1,
        requirement_id: r.id,
        created_at: createdAt,
        last_modified: lastModified,
        model_selected: selectedTemplate
          ? {
              id: selectedTemplate.id,
              type: selectedTemplate.type,
              modality: selectedTemplate.modality,
              communicative_function: selectedTemplate.communicative_function,
              structural_template: selectedTemplate.structural_template
            }
          : {
              id: r.templateId || null,
              type: 'undefined',
              modality: 'any',
              communicative_function: 'any',
              structural_template: '<sentence>'
            },
        original_sentence:
          (r as any)?.originalSentence ||
          (r as any)?.state?.values?.['sentence'] ||
          '',
        generated_sentence: r.sentence,
        triples: (r as any)?.triples ?? [],
        commodity: commodityText,
        commodities
      };
    });

    const exportData = {
      version: '2.0',
      exported_at: new Date().toISOString(),
      total_requirements: requirementsExport.length,
      requirements: requirementsExport
    };

    const rows = requirementsExport.map(item => ({
      order: item.order,
      requirement_id: item.requirement_id,
      template_id: item.model_selected?.id ?? '',
      template_type: item.model_selected?.type ?? '',
      modality: item.model_selected?.modality ?? '',
      communicative_function: item.model_selected?.communicative_function ?? '',
      structural_template: item.model_selected?.structural_template ?? '',
      original_sentence: item.original_sentence ?? '',
      generated_sentence: item.generated_sentence ?? '',
      triples: (item.triples ?? [])
        .map((t: any) => `${t.subject} | ${t.predicate} | ${t.object}`)
        .join(' ; '),
      commodity: item.commodity ?? '',
      commodities: (item as any).commodities?.join(' | ') ?? '',
      created_at: item.created_at ?? '',
      last_modified: item.last_modified ?? ''
    }));

    const timestamp = Date.now();
    const baseName = `requirements_full_processing_${timestamp}`;

    if (format === 'json') {
      this.downloadBlob(
        new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' }),
        `${baseName}.json`
      );
      return;
    }

    if (format === 'csv') {
      const headers = Object.keys(rows[0] ?? {});
      const csvLines = [
        headers.join(','),
        ...rows.map(row =>
          headers
            .map(h => `"${String((row as any)[h] ?? '').replace(/"/g, '""')}"`)
            .join(',')
        )
      ];
      this.downloadBlob(new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' }), `${baseName}.csv`);
      return;
    }

    if (format === 'md') {
      const md = requirementsExport
        .map(item => {
          const triples = (item.triples ?? [])
            .map((t: any) => `- ${t.subject} | ${t.predicate} | ${t.object}`)
            .join('\n');
          const model = item.model_selected ?? { id: '' };

          return [
            `## Requirement ${item.order}`,
            `- ID: ${item.requirement_id}`,
            `- Template ID: ${model.id ?? ''}`,
            `- Template Type: ${(model as any).type ?? ''}`,
            `- Modality: ${(model as any).modality ?? ''}`,
            `- Communicative Function: ${(model as any).communicative_function ?? ''}`,
            `- Structural Template: ${(model as any).structural_template ?? ''}`,
            `- Original Sentence: ${item.original_sentence ?? ''}`,
            `- Generated Sentence: ${item.generated_sentence ?? ''}`,
            `- Commodity: ${item.commodity ?? ''}`,
            `- Commodities: ${((item as any).commodities ?? []).join(', ')}`,
            `- Created At: ${item.created_at ?? ''}`,
            `- Last Modified: ${item.last_modified ?? ''}`,
            `- Triples:`,
            triples || '- (none)',
            ''
          ].join('\n');
        })
        .join('\n');

      this.downloadBlob(new Blob([md], { type: 'text/markdown;charset=utf-8;' }), `${baseName}.md`);
      return;
    }

    if (format === 'text') {
      const text = requirementsExport
        .map(item => {
          const triples = (item.triples ?? [])
            .map((t: any) => `  - ${t.subject} | ${t.predicate} | ${t.object}`)
            .join('\n');
          const model = item.model_selected ?? { id: '' };

          return [
            `Requirement ${item.order}`,
            `ID: ${item.requirement_id}`,
            `Template ID: ${model.id ?? ''}`,
            `Template Type: ${(model as any).type ?? ''}`,
            `Modality: ${(model as any).modality ?? ''}`,
            `Communicative Function: ${(model as any).communicative_function ?? ''}`,
            `Structural Template: ${(model as any).structural_template ?? ''}`,
            `Original Sentence: ${item.original_sentence ?? ''}`,
            `Generated Sentence: ${item.generated_sentence ?? ''}`,
            `Commodity: ${item.commodity ?? ''}`,
            `Commodities: ${((item as any).commodities ?? []).join(', ')}`,
            `Created At: ${item.created_at ?? ''}`,
            `Last Modified: ${item.last_modified ?? ''}`,
            `Triples:`,
            triples || '  - (none)',
            ''
          ].join('\n');
        })
        .join('\n');

      this.downloadBlob(new Blob([text], { type: 'text/plain;charset=utf-8;' }), `${baseName}.txt`);
      return;
    }

    if (format === 'xlsx') {
      const XLSX = await import('xlsx');
      const worksheet = XLSX.utils.json_to_sheet(rows);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'requirements');
      const workbookArray = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      this.downloadBlob(
        new Blob([workbookArray], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }),
        `${baseName}.xlsx`
      );
    }
  }

  private downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  private resolveTemplateForExport(req: RequirementItem): TemplateItem | undefined {
    const snapshot = (req as any)?.templateSnapshot as TemplateItem | undefined;
    if (snapshot) return snapshot;

    const byId = this.allTemplates.find(t => t.id === req.templateId);
    if (byId) return byId;

    if (req.templateId === 'UND-00') {
      return this.allTemplates.find(t => t.id === this.UND_TEMPLATE_ID);
    }

    return undefined;
  }

  /* =========================
   * EXPORT / IMPORT TEMPLATES
   * ========================= */
  
  /**
   * Exports templates used in requirements as custom templates
   */
  exportTemplates(): void {
    // Get unique template IDs from requirements
    const usedTemplateIds = new Set<string>();
    for (const req of this.requirements) {
      if (req.templateId && req.templateId !== 'UND-00') {
        usedTemplateIds.add(req.templateId);
      }
    }

    // Find the actual template objects
    const templatesToExport = this.allTemplates.filter(t => 
      usedTemplateIds.has(t.id)
    );

    if (templatesToExport.length === 0) {
      this.showToast('No templates to export', 'info');
      return;
    }

    // Create export object
    const exportData = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      templates: templatesToExport
    };

    // Download as JSON
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `custom_templates_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    this.showToast(`Exported ${templatesToExport.length} template(s)`, 'success');
  }

  /**
   * Exports ALL custom templates (imported or created, not original)
   */
  exportAllCustomTemplates(): void {
    // Get all custom templates using the customTemplateIds set
    const customTemplates = this.allTemplates.filter(t => 
      this.customTemplateIds.has(t.id)
    );

    if (customTemplates.length === 0) {
      this.showToast('No custom templates to export', 'info');
      return;
    }

    // Create enhanced export object with metadata
    const exportData = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      total_templates: customTemplates.length,
      metadata: {
        export_type: 'all_custom',
        template_sources: customTemplates.map(t => ({
          id: t.id,
          source: this.templateMetadata.get(t.id)?.source || 'unknown',
          added_at: this.templateMetadata.get(t.id)?.addedAt || 'unknown'
        }))
      },
      templates: customTemplates
    };

    // Download as JSON
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `all_custom_templates_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    this.showToast(`Exported ${customTemplates.length} custom template(s)`, 'success');
  }

  /**
   * Triggers the file input for importing templates
   */
  triggerImportTemplates(): void {
    this.importFileInput.nativeElement.click();
  }

  /**
   * Handles the file import event
   */
  handleImportFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];

    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const importData = JSON.parse(content);

        // Validate structure
        if (!importData.templates || !Array.isArray(importData.templates)) {
          this.showToast('Invalid template file format', 'error');
          return;
        }

        // Import templates
        let importedCount = 0;
        const now = new Date().toISOString();
        
        for (const rawTemplate of importData.templates) {
          const template = this.crd13Api.normalizeTemplateForFrontend(rawTemplate);

          // Check if template already exists
          const exists = this.allTemplates.some(t => t.id === template.id);
          
          if (!exists) {
            // Ensure imported templates are marked as custom type
            template.type = 'custom';
            this.allTemplates.push(template);
            
            // Register as custom imported template
            this.customTemplateIds.add(template.id);
            this.templateMetadata.set(template.id, {
              source: 'imported',
              addedAt: now,
              usedInRequirements: []
            });
            
            importedCount++;
          }
        }

        if (importedCount > 0) {
          // Rebuild filters and apply
          this.buildFilterOptions();
          this.applyFilters();
          
          this.showToast(`Imported ${importedCount} new template(s)`, 'success');
        } else {
          this.showToast('All templates already exist', 'info');
        }

      } catch (error) {
        console.error('Error importing templates:', error);
        this.showToast('Failed to import templates', 'error');
      } finally {
        // Reset file input
        input.value = '';
      }
    };

    reader.readAsText(file);
  }

  /* =========================
   * TEMPLATE METADATA (mvp-4.0)
   * ========================= */
  getComponentMeta(label: string): TemplateComponent | undefined {
    const comps = this.selectedTemplate?.components;
    if (!comps) return undefined;
    return Object.values(comps).find(c => c.label === label);
  }

  isComponentEdited(name: string): boolean {
    return this.editedComponents.has(name);
  }

  getComponentDisplayValue(name: string): string {
    if (!this.isComponentEdited(name)) return `<${name}>`;
    return this.state.values[name] || '...';
  }

  getComponentTooltip(token: any): string {
    const name = token.name;
    if (!this.isComponentEdited(name)) {
      const meta = this.getComponentMeta(name);
      return meta?.examples?.[0] || `<${name}>`;
    }
    return `<${name}>`;
  }

  /**
   * Returns true if a template is of type 'custom' (user-created, imported, or AI-generated)
   */
  isCustomTemplate(template: TemplateItem): boolean {
    return template.type === 'custom' || this.customTemplateIds.has(template.id);
  }

  /* =========================
   * SUGGEST TEMPLATE (API)
   * ========================= */
  async suggestTemplate() {
    try {
      this.suggesting = true;
      this.error = null;

      // Use the current requirement sentence if you have one;
      // fallback to generatedSentence.
      const text =
        (this.generatedSentence || '').trim() ||
        (this.state?.values?.['sentence'] || '').trim();

      if (!text) {
        this.error = 'No text to suggest a template for.';
        return;
      }

      const res = await firstValueFrom(
        this.crd13Api.adaptAttestationTemplate(text)
      );

      this.applySuggestedTemplate(res);

    } catch (e: any) {
      this.error = e?.message || 'Failed to suggest template.';
    } finally {
      this.suggesting = false;
    }
  }

  /**
   * Auto-suggest template for a specific requirement (used when editing an UND-00 requirement).
   */
  private async suggestTemplateForRequirement(req: RequirementItem): Promise<void> {
    try {
      this.suggesting = true;
      this.error = null;

      const text = String(
        (req as any)?.originalSentence ||
        (req as any)?.state?.values?.['sentence'] ||
        req.sentence ||
        ''
      ).trim();

      if (!text) {
        this.error = 'No text to suggest a template for.';
        return;
      }

      const res = await firstValueFrom(
        this.crd13Api.adaptAttestationTemplate(text)
      );

      // Persist and show original sentence
      this.currentOriginalSentence = res?.sentence?.trim() || text;
      (req as any).originalSentence = this.currentOriginalSentence;

      // Apply suggestion to the editor
      console.log(res);
      this.applySuggestedTemplate(res);

      // Keep the card in "editing" state
      this.editingRequirementId = req.id;
    } catch (e: any) {
      this.error = e?.message || 'Failed to suggest template.';
    } finally {
      this.suggesting = false;
    }
  }

  /**
   * Suggests a template for the requirement but does NOT fill in values (keeps tags empty).
   * Used when the user clicks to edit a requirement with an undefined template (UND).
   * After suggestion, persists the identified templateId on the requirement so AI
   * is never called again for the same requirement.
   */
  private async suggestTemplateForRequirementTagsOnly(req: RequirementItem, sessionId: number): Promise<void> {
    this.suggestionLoading = true;
    this.error = null;

    try {
      const text = String(
        (req as any)?.originalSentence ||
        (req as any)?.state?.values?.['sentence'] ||
        req.sentence ||
        ''
      ).trim();

      if (!text) {
        this.error = 'No text to suggest a template for.';
        return;
      }

      const res = await firstValueFrom(
        this.crd13Api.adaptAttestationTemplate(text)
      );

      // Ignore stale responses from an older edit click.
      if (sessionId !== this.editSessionId || this.editingRequirementId !== req.id) {
        return;
      }

      const suggested = res?.template;
      console.log(text);
      console.log('Suggested template:', suggested, 'for text:', text);
      if (!suggested?.id) return;

      // Persist original sentence
      this.currentOriginalSentence = res?.sentence?.trim() || text;
      (req as any).originalSentence = this.currentOriginalSentence;

      // If API created a new template, merge it into allTemplates
      if (res.created_new) {
        const exists = this.allTemplates.some(t => t.id === suggested.id);
        if (!exists) {
          suggested.type = 'custom';
          this.allTemplates = [...this.allTemplates, suggested];
          this.customTemplateIds.add(suggested.id);
          this.templateMetadata.set(suggested.id, {
            source: 'created',
            addedAt: new Date().toISOString(),
            usedInRequirements: []
          });
          this.buildFilterOptions();
        }
      }

      // Sync sidebar to suggested template
      this.selectedModality = suggested.modality || 'any';
      this.selectedFunction = suggested.communicative_function || 'any';
      this.applyFiltersInternal();

      // Get template from store
      const templateFromStore = this.allTemplates.find(t => t.id === suggested.id) || suggested;

      // Apply only the template structure - do NOT fill values, keep tags empty
      this.selectedTemplateId = templateFromStore.id;
      this.selectedTemplate = templateFromStore;
      this.tokens = this.parser.parseTemplate(templateFromStore.structural_template);
      this.collected = this.parser.collectElements(this.tokens);
      this.resetState(); // resets state without filling values from suggestion
      this.editedComponents.clear();

      // Re-pin editing id
      this.editingRequirementId = req.id;

      // ── KEY FIX: persist the identified templateId on the requirement immediately ──
      // This ensures the next time editRequirement() is called, isUndefined === false
      // and the AI is NOT triggered again.
      const reqIdx = this.requirements.findIndex(r => r.id === req.id);
      if (reqIdx >= 0) {
        this.requirements[reqIdx] = {
          ...this.requirements[reqIdx],
          templateId: templateFromStore.id,
          templateSnapshot: JSON.parse(JSON.stringify(templateFromStore)),
          lastModified: new Date().toISOString()
        } as any;
      }

      // Update display
      this.updateAll();
      this.closePopover();

    } catch (e: any) {
      this.error = e?.message || 'Failed to suggest template.';
    } finally {
      this.suggestionLoading = false;
    }
  }


  async createNewTemplate(): Promise<void> {
    try {
      this.suggesting = true;
      this.error = null;

      const text = (this.generatedSentence || '').trim();

      if (!text) {
        this.error = 'No sentence to create template from.';
        return;
      }

      const res = await firstValueFrom(
        this.crd13Api.adaptAttestationTemplate(text)
      );

      // Add new template to list if successful
      if (res?.template?.id) {
        const exists = this.allTemplates.some(t => t.id === res.template.id);
        if (!exists) {
          // Mark as custom type
          res.template.type = 'custom';
          this.allTemplates = [...this.allTemplates, res.template];
          
          // Register as custom created template
          this.customTemplateIds.add(res.template.id);
          this.templateMetadata.set(res.template.id, {
            source: 'created',
            addedAt: new Date().toISOString(),
            usedInRequirements: []
          });
          
          this.buildFilterOptions();
          this.applyFilters();
        }
        
        // Optionally select the new template
        this.selectTemplate(res.template);
      }

      this.showToast('New template created successfully!', 'success');
    } catch (e: any) {
      this.error = e?.message || 'Failed to create template.';
      this.showToast('Error creating template: ' + (e?.message || 'Unknown error'), 'error');
    } finally {
      this.suggesting = false;
    }
  }

  /**
   * APPLY TEMPLATE: Identify and apply template to current generated sentence
   */
  async applyTemplateToSentence(): Promise<void> {
    try {
      this.suggesting = true;
      this.error = null;

      const text = (this.generatedSentence || '').trim();

      if (!text) {
        this.error = 'No sentence to apply template to.';
        return;
      }

      const res = await firstValueFrom(
        this.crd13Api.adaptAttestationTemplate(text)
      );

      // Apply the identified template
      this.applySuggestedTemplate(res);

      // Show original sentence
      if (res?.sentence?.trim()) {
        this.currentOriginalSentence = res.sentence.trim();
      }
    } catch (e: any) {
      this.error = e?.message || 'Failed to apply template.';
      this.showToast('Error applying template: ' + (e?.message || 'Unknown error'), 'error');
    } finally {
      this.suggesting = false;
    }
  }

  private applySuggestedTemplate(res: IdentifyTemplateResponse) {
    const suggested = res?.template;
    if (!suggested?.id) {
      this.error = 'Template suggestion returned no template.';
      return;
    }

    // If API created a new template, merge it into allTemplates
    if (res.created_new) {
      const exists = this.allTemplates.some(t => t.id === suggested.id);
      if (!exists) {
        // Mark as custom type
        suggested.type = 'custom';
        this.allTemplates = [...this.allTemplates, suggested];
        
        // Register as custom created template
        this.customTemplateIds.add(suggested.id);
        this.templateMetadata.set(suggested.id, {
          source: 'created',
          addedAt: new Date().toISOString(),
          usedInRequirements: []
        });
        
        this.buildFilterOptions();
      }
    }

    // 1) Sync sidebar dropdowns to suggested template
    this.selectedModality = suggested.modality || 'any';
    this.selectedFunction = suggested.communicative_function || 'any';

    // 2) Re-filter list so sidebar shows the right options/count
    this.applyFilters();

    // 3) Select the actual template instance from allTemplates (preferred)
    const templateFromStore =
      this.allTemplates.find(t => t.id === suggested.id) || suggested;

    this.selectTemplate(templateFromStore);

    // 4) Fill state from suggested components and mark them as edited
    // IMPORTANT: do this AFTER selectTemplate(), because selectTemplate() calls resetState()
    for (const c of Object.values(suggested.components || {})) {
      if (!c?.label) continue;

      this.state.values[c.label] = String(c.text ?? '');
      this.editedComponents.add(c.label);
    }

    // 5) Now force full recompute (preview + generatedSentence + validation)
    this.updateAll();

    // Keep the original sentence for display (do NOT overwrite generatedSentence)
    if (res.sentence?.trim()) {
      this.currentOriginalSentence = res.sentence.trim();
    }

    // If popover is open, close it (prevents stale editor context)
    this.closePopover();
  }

  /* =========================
   * REWRITE ATTESTATION MODAL
   * ========================= */

  /**
   * Opens the Rewrite modal pre-loaded with the current generated sentence
   */
  openRewriteModal(): void {
    const sentence = this.currentOriginalSentence || this.generatedSentence;
    if (!sentence) return;
    this.rewriteSentence = sentence;
    if (this.editingRequirementId) {
      const req = this.requirements.find(r => r.id === this.editingRequirementId);
      this.rewriteCommodities = this.normalizeCommodities(
        (req as any)?.commodities ?? (req as any)?.commodity ?? this.rewriteCommodities
      );
    }
    this.rewriteModalVisible = true;
  }

  /**
   * Closes the Rewrite modal
   */
  closeRewriteModal(): void {
    this.rewriteModalVisible = false;
    this.rewriteSentence = '';
  }

  onRewriteCommodityChanged(commodities: string[]): void {
    this.rewriteCommodities = this.normalizeCommodities(commodities);

    if (!this.editingRequirementId) return;

    const idx = this.requirements.findIndex(r => r.id === this.editingRequirementId);
    if (idx >= 0) {
      this.requirements[idx] = {
        ...this.requirements[idx],
        commodity: this.serializeCommodities(this.rewriteCommodities),
        commodities: this.rewriteCommodities,
        lastModified: new Date().toISOString()
      } as any;
    }
  }

  /**
   * Applies the rewritten sentence to the current requirement's generated sentence.
   * Updates the free-text component value so the editor stays in sync.
   */
  onRewriteApplied(result: RewriteResult): void {
    this.closeRewriteModal();

    // Sync selected template metadata/pattern when rewrite suggests changes.
    this.applyRewriteTemplateChanges(result);

    // Fit rewritten text into the active/suggested template structure.
    const fittedToTemplate = this.fitRewriteTextIntoTemplate(result.text);

    // Persist as the "sentence" component so auto-save works correctly
    this.state.values['sentence'] = result.text;
    this.editedComponents.add('sentence');
    this.updateAll();
    if (!fittedToTemplate && result.text?.trim() && this.generatedSentence.trim() !== result.text.trim()) {
      this.generatedSentence = result.text;
    }
    const appliedSentence = (this.generatedSentence || result.text || '').trim();
    const resultCommodities = this.normalizeCommodities(result.commodity ?? this.rewriteCommodities);

    // If editing an existing requirement, update it in-place immediately
    if (this.editingRequirementId) {
      const idx = this.requirements.findIndex(r => r.id === this.editingRequirementId);
      if (idx >= 0) {
        this.requirements[idx] = {
          ...this.requirements[idx],
          templateId: this.selectedTemplate?.id || this.requirements[idx].templateId,
          sentence: appliedSentence,
          state: JSON.parse(JSON.stringify(this.state)),
          templateSnapshot: this.selectedTemplate ? JSON.parse(JSON.stringify(this.selectedTemplate)) : (this.requirements[idx] as any).templateSnapshot,
          commodity: this.serializeCommodities(resultCommodities),
          commodities: resultCommodities,
          lastModified: new Date().toISOString()
        } as any;
      }
    }

    this.rewriteCommodities = resultCommodities;

    this.showToast('Rewrite applied', 'success');
  }

  /**
   * Applies template changes coming from rewrite result, when present.
   * Keeps current editor state and reparses the preview if structure changes.
   */
  private applyRewriteTemplateChanges(result: RewriteResult): void {
    if (!this.selectedTemplate) return;

    let changed = false;

    const nextTemplate = (result.template || '').trim();
    if (nextTemplate && nextTemplate !== this.selectedTemplate.structural_template) {
      this.selectedTemplate.structural_template = nextTemplate;
      this.tokens = this.parser.parseTemplate(nextTemplate);
      this.collected = this.parser.collectElements(this.tokens);

      // Ensure state keeps required keys after template structure update.
      for (const opt of this.collected.optionals) {
        if (this.state.optionals[opt.id] == null) {
          this.state.optionals[opt.id] = false;
        }
      }
      for (const choice of this.collected.choices) {
        if (!this.state.choices[choice.id]) {
          this.state.choices[choice.id] = choice.options[0] || '';
        }
      }
      for (const comp of this.collected.components) {
        if (this.state.values[comp.name] == null) {
          const meta = this.getComponentMeta(comp.name);
          this.state.values[comp.name] = meta?.text || meta?.examples?.[0] || '';
        }
      }

      changed = true;
    }

    const nextModality = (result.modality || '').trim();
    if (nextModality && nextModality !== this.selectedTemplate.modality) {
      this.selectedTemplate.modality = nextModality;
      this.selectedModality = nextModality;
      changed = true;
    }

    const nextFunction = (result.communicative_function || '').trim();
    if (nextFunction && nextFunction !== this.selectedTemplate.communicative_function) {
      this.selectedTemplate.communicative_function = nextFunction;
      this.selectedFunction = nextFunction;
      changed = true;
    }

    if (changed) {
      this.updateFunctionOptions();
      this.applyFiltersInternal();
    }
  }

  /**
   * Tries to fit a free-text rewrite into the current template by mapping
   * captured groups to template components and choices.
   */
  private fitRewriteTextIntoTemplate(text: string): boolean {
    const target = String(text || '').trim();
    if (!target || this.tokens.length === 0) return false;

    const captures: Array<{ kind: 'component' | 'choice'; id: string }> = [];
    const pattern = this.buildTemplateRegex(this.tokens, captures);
    if (!pattern) return false;

    let match: RegExpMatchArray | null = null;
    try {
      match = target.match(new RegExp(`^\\s*${pattern}\\s*$`, 'i'));
    } catch {
      return false;
    }
    if (!match) return false;

    for (let i = 0; i < captures.length; i++) {
      const meta = captures[i];
      const raw = (match[i + 1] || '').trim();
      if (!raw) continue;

      if (meta.kind === 'component') {
        this.state.values[meta.id] = raw.replace(/\s+/g, ' ');
        this.editedComponents.add(meta.id);
      } else {
        this.state.choices[meta.id] = raw;
      }
    }

    return true;
  }

  private buildTemplateRegex(
    tokens: Token[],
    captures: Array<{ kind: 'component' | 'choice'; id: string }>
  ): string {
    const parts: string[] = [];

    for (const token of tokens) {
      if (token.type === 'text') {
        const text = this.escapeRegex(token.value || '').replace(/\s+/g, '\\s+');
        if (text) parts.push(text);
        continue;
      }

      if (token.type === 'component') {
        captures.push({ kind: 'component', id: token.name || '' });
        parts.push('(.+?)');
        continue;
      }

      if (token.type === 'choice') {
        const options = (token.options || [])
          .map(opt => this.escapeRegex(opt).replace(/\s+/g, '\\s+'))
          .filter(Boolean)
          .join('|');

        if (!options) continue;

        captures.push({ kind: 'choice', id: token.id || '' });
        parts.push(`(${options})`);
        continue;
      }

      if (token.type === 'optional') {
        const childPattern = this.buildTemplateRegex(token.children || [], captures);
        if (childPattern) {
          parts.push(`(?:${childPattern})?`);
        }
      }
    }

    return parts.join('');
  }

  private escapeRegex(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  private normalizeCommodities(input: unknown): string[] {
    if (Array.isArray(input)) {
      const normalized = input
        .map(item => String(item ?? '').trim())
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

    const text = String(input ?? '').trim();
    if (!text) return [];
    return text
      .split(',')
      .map(item => item.trim())
      .filter(Boolean);
  }

  private serializeCommodities(commodities: string[]): string {
    const normalized = this.normalizeCommodities(commodities);
    return normalized.join(', ');
  }

  /* =========================
   * INSPECTION / DEBUG
   * ========================= */
  toggleDebug(): void {
    this.debugOpen = !this.debugOpen;
  }

  getDebugJson(): string {
    try {
      return JSON.stringify(this.getDebugObject(), null, 2);
    } catch {
      return '{"error":"failed_to_stringify"}';
    }
  }

  logDebugToConsole(): void {
    // eslint-disable-next-line no-console
    console.log('[PageReviewer Debug]', this.getDebugObject());
  }

  copyDebugJson(): void {
    navigator.clipboard.writeText(this.getDebugJson());
  }

  copyOriginalSentence(): void {
    if (!this.currentOriginalSentence) return;
    navigator.clipboard.writeText(this.currentOriginalSentence);
  }

  showRequirementTooltip(event: MouseEvent, text: string): void {
    const tooltipText = String(text ?? '').trim();
    if (!tooltipText) return;

    const target = event.currentTarget as HTMLElement | null;
    const rect = target?.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const estimatedWidth = Math.min(360, Math.max(220, viewportWidth * 0.45));
    const anchorLeft = rect ? rect.left : event.clientX;
    const anchorTop = rect ? rect.top : event.clientY;
    const anchorBottom = rect ? rect.bottom : event.clientY;

    this.requirementTooltipText = tooltipText;
    this.requirementTooltipX = Math.min(
      Math.max(12, anchorLeft),
      Math.max(12, viewportWidth - estimatedWidth - 12)
    );
    this.requirementTooltipY = anchorTop > 96 ? anchorTop - 12 : anchorBottom + 12;
    this.requirementTooltipVisible = true;
  }

  hideRequirementTooltip(): void {
    this.requirementTooltipVisible = false;
  }

  private getDebugObject(): any {
    const editing = this.editingRequirementId
      ? this.requirements.find(r => r.id === this.editingRequirementId)
      : null;

    return {
      uiStep: this.uiStep,
      selectedModality: this.selectedModality,
      selectedFunction: this.selectedFunction,
      selectedTemplateId: this.selectedTemplateId,
      selectedTemplate: this.selectedTemplate,
      editingRequirementId: this.editingRequirementId,
      editingRequirement: editing,
      currentOriginalSentence: this.currentOriginalSentence,
      generatedSentence: this.generatedSentence,
      validationProblems: this.validationProblems,
      state: this.state,
      collected: this.collected,
      tokens: this.tokens,
      suggesting: this.suggesting,
      error: this.error,
      templatesCount: this.allTemplates.length,
      filteredTemplatesCount: this.filteredTemplates.length,
      requirementsCount: this.requirements.length,
    };
  }

  private stopEditingRequirement(reason: 'filters_changed' | 'manual' = 'manual'): void {
    if (!this.editingRequirementId) return;
    this.editingRequirementId = null;
    this.currentOriginalSentence = '';
    this.rewriteCommodities = [];
    // eslint-disable-next-line no-console
    console.debug('[PageReviewer] stopEditingRequirement:', reason);
  }

  /* =========================
   * TEMPLATE EDITING FUNCTIONS
   * ========================= */
  
  /**
   * Opens modal to add a new component to the current template
   */
  openAddComponentModal(): void {
    if (!this.selectedTemplate) return;
    
    // Reset form
    this.newComponent = {
      label: '',
      text: '',
      description: '',
      examplesText: '',
      required: false,
      allowCustom: true
    };
    
    this.addComponentModalVisible = true;
  }

  /**
   * Closes the add component modal
   */
  closeAddComponentModal(): void {
    this.addComponentModalVisible = false;
  }

  /**
   * Saves the new component to the template
   */
  saveNewComponent(): void {
    if (!this.newComponent.label || !this.selectedTemplate) return;

    // Parse examples from comma-separated string
    const examples = this.newComponent.examplesText
      .split(',')
      .map(e => e.trim())
      .filter(Boolean);

    // Create component object
    const componentKey = this.newComponent.label.toLowerCase().replace(/\s+/g, '_');
    const component = {
      label: this.newComponent.label,
      text: this.newComponent.text || '',
      description: this.newComponent.description || '',
      examples: examples,
      required: this.newComponent.required,
      allow_custom: this.newComponent.allowCustom
    };

    // Add to template's components
    if (!this.selectedTemplate.components) {
      this.selectedTemplate.components = {};
    }
    this.selectedTemplate.components[componentKey] = component;

    // Add component placeholder to structural template
    const marker = this.newComponent.required ? '*' : '';
    const placeholder = `${marker}<${this.newComponent.label}>`;
    
    // Append to end of structural template (before any closing brackets if they exist)
    if (this.selectedTemplate.structural_template) {
      this.selectedTemplate.structural_template += ' ' + placeholder;
    } else {
      this.selectedTemplate.structural_template = placeholder;
    }

    // Reparse template
    this.tokens = this.parser.parseTemplate(this.selectedTemplate.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    // Initialize state for new component
    this.state.values[this.newComponent.label] = this.newComponent.text || '';

    // Update display
    this.updateAll();
    
    // Close modal
    this.closeAddComponentModal();
  }

  /**
   * Opens modal to delete a component from the template
   */
  deleteComponentFromTemplate(): void {
    if (!this.selectedTemplate) return;

    // Get list of all components
    this.availableComponentsForDeletion = this.collected.components.map(c => c.name);
    
    // Reset selection
    this.componentToDelete = '';
    
    // Open modal
    this.deleteComponentModalVisible = true;
  }

  /**
   * Closes the delete component modal
   */
  closeDeleteComponentModal(): void {
    this.deleteComponentModalVisible = false;
    this.componentToDelete = '';
    this.availableComponentsForDeletion = [];
  }

  /**
   * Confirms and executes the deletion of selected component
   */
  confirmDeleteComponent(): void {
    if (!this.componentToDelete || !this.selectedTemplate) return;

    const found = this.componentToDelete;

    // Remove from structural template
    // Look for patterns like: <componentName>, *<componentName>
    let updatedTemplate = this.selectedTemplate.structural_template || '';
    
    // Remove with optional * prefix and surrounding spaces
    const patterns = [
      new RegExp(`\\s*\\*?<${found}>\\s*`, 'gi'),
      new RegExp(`\\s*<${found}>\\s*`, 'gi')
    ];

    for (const pattern of patterns) {
      updatedTemplate = updatedTemplate.replace(pattern, ' ');
    }

    // Clean up extra spaces
    updatedTemplate = updatedTemplate.replace(/\s+/g, ' ').trim();

    this.selectedTemplate.structural_template = updatedTemplate;

    // Remove from components object
    if (this.selectedTemplate.components) {
      const componentKey = found.toLowerCase().replace(/\s+/g, '_');
      delete this.selectedTemplate.components[componentKey];
    }

    // Reparse template
    this.tokens = this.parser.parseTemplate(this.selectedTemplate.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    // Remove from state
    delete this.state.values[found];
    this.editedComponents.delete(found);

    // Update display
    this.updateAll();

    // Close modal
    this.closeDeleteComponentModal();
  }

  /* =========================
   * CHOICE EDITING FUNCTIONS
   * ========================= */

  /**
   * Opens modal to add a new choice to the current template
   */
  openAddChoiceModal(): void {
    if (!this.selectedTemplate) return;
    
    // Reset form
    this.newChoice = {
      optionsText: '',
      required: false
    };
    
    this.addChoiceModalVisible = true;
  }

  /**
   * Closes the add choice modal
   */
  closeAddChoiceModal(): void {
    this.addChoiceModalVisible = false;
  }

  /**
   * Validates if choice options text is valid
   */
  isValidChoiceOptions(): boolean {
    const text = this.newChoice.optionsText.trim();
    if (!text) return false;
    
    const options = text.split('/').map(o => o.trim()).filter(Boolean);
    return options.length >= 2;
  }

  /**
   * Gets preview text for the choice
   */
  getChoicePreview(): string {
    const text = this.newChoice.optionsText.trim();
    if (!text) return '';
    
    const marker = this.newChoice.required ? '*' : '';
    return `${marker}[${text}]`;
  }

  /**
   * Saves the new choice to the template
   */
  saveNewChoice(): void {
    if (!this.isValidChoiceOptions() || !this.selectedTemplate) return;

    // Parse options
    const options = this.newChoice.optionsText
      .split('/')
      .map(o => o.trim())
      .filter(Boolean);

    // Build choice placeholder
    const marker = this.newChoice.required ? '*' : '';
    const placeholder = `${marker}[${options.join('/')}]`;
    
    // Append to structural template
    if (this.selectedTemplate.structural_template) {
      this.selectedTemplate.structural_template += ' ' + placeholder;
    } else {
      this.selectedTemplate.structural_template = placeholder;
    }

    // Reparse template
    this.tokens = this.parser.parseTemplate(this.selectedTemplate.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    // Initialize state for new choice (set to first option)
    const newChoiceId = this.collected.choices[this.collected.choices.length - 1]?.id;
    if (newChoiceId) {
      this.state.choices[newChoiceId] = options[0];
    }

    // Update display
    this.updateAll();
    
    // Close modal
    this.closeAddChoiceModal();
  }

  /**
   * Opens modal to delete a choice from the template
   */
  deleteChoiceFromTemplate(): void {
    if (!this.selectedTemplate) return;

    // Build list of choices with their display text
    this.availableChoicesForDeletion = this.collected.choices.map(c => ({
      id: c.id,
      displayText: `[${c.options.join('/')}]`,
      options: c.options
    }));
    
    // Reset selection
    this.choiceToDelete = '';
    
    // Open modal
    this.deleteChoiceModalVisible = true;
  }

  /**
   * Closes the delete choice modal
   */
  closeDeleteChoiceModal(): void {
    this.deleteChoiceModalVisible = false;
    this.choiceToDelete = '';
    this.availableChoicesForDeletion = [];
  }

  /**
   * Confirms and executes the deletion of selected choice
   */
  confirmDeleteChoice(): void {
    if (!this.choiceToDelete || !this.selectedTemplate) return;

    // Find the choice to delete
    const choiceData = this.availableChoicesForDeletion.find(
      c => c.displayText === this.choiceToDelete
    );

    if (!choiceData) return;

    // Remove from structural template
    let updatedTemplate = this.selectedTemplate.structural_template || '';
    
    // Build patterns to match: [options], *[options]
    const optionsPattern = choiceData.options.join('/').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const patterns = [
      new RegExp(`\\s*\\*?\\[${optionsPattern}\\]\\s*`, 'gi'),
      new RegExp(`\\s*\\[${optionsPattern}\\]\\s*`, 'gi')
    ];

    for (const pattern of patterns) {
      updatedTemplate = updatedTemplate.replace(pattern, ' ');
    }

    // Clean up extra spaces
    updatedTemplate = updatedTemplate.replace(/\s+/g, ' ').trim();

    this.selectedTemplate.structural_template = updatedTemplate;

    // Reparse template
    this.tokens = this.parser.parseTemplate(this.selectedTemplate.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    // Remove from state
    delete this.state.choices[choiceData.id];

    // Update display
    this.updateAll();

    // Close modal
    this.closeDeleteChoiceModal();
  }

  /* =========================
   * TEXT EDITING FUNCTIONS
   * ========================= */

  /**
   * Opens modal to add immutable text to the current template
   */
  openAddTextModal(): void {
    if (!this.selectedTemplate) return;
    
    // Reset form
    this.newText = {
      content: ''
    };
    
    this.addTextModalVisible = true;
  }

  /**
   * Closes the add text modal
   */
  closeAddTextModal(): void {
    this.addTextModalVisible = false;
  }

  /**
   * Saves the new text to the template
   */
  saveNewText(): void {
    const text = this.newText.content?.trim();
    if (!text || !this.selectedTemplate) return;

    // Append text to structural template
    if (this.selectedTemplate.structural_template) {
      this.selectedTemplate.structural_template += ' ' + text;
    } else {
      this.selectedTemplate.structural_template = text;
    }

    // Reparse template
    this.tokens = this.parser.parseTemplate(this.selectedTemplate.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    // Update display
    this.updateAll();
    
    // Close modal
    this.closeAddTextModal();
  }

  /**
   * Opens modal to delete text from the template
   */
  deleteTextFromTemplate(): void {
    if (!this.selectedTemplate) return;

    // Extract text fragments from tokens (only text type with 2+ words)
    const textFragments: string[] = [];
    
    for (const token of this.tokens) {
      if (token.type === 'text' && token.value) {
        const trimmed = token.value.trim();
        // Only show text fragments with at least 2 words (to avoid punctuation)
        const wordCount = trimmed.split(/\s+/).length;
        if (wordCount >= 2) {
          textFragments.push(trimmed);
        }
      }
    }

    this.availableTextsForDeletion = textFragments;
    
    // Reset selection
    this.textToDelete = '';
    
    // Open modal
    this.deleteTextModalVisible = true;
  }

  /**
   * Closes the delete text modal
   */
  closeDeleteTextModal(): void {
    this.deleteTextModalVisible = false;
    this.textToDelete = '';
    this.availableTextsForDeletion = [];
  }

  /**
   * Confirms and executes the deletion of selected text
   */
  confirmDeleteText(): void {
    if (!this.textToDelete || !this.selectedTemplate) return;

    // Remove from structural template
    let updatedTemplate = this.selectedTemplate.structural_template || '';
    
    // Escape special regex characters in the text to delete
    const escapedText = this.textToDelete.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    
    // Remove the text (with optional surrounding spaces)
    const pattern = new RegExp(`\\s*${escapedText}\\s*`, 'gi');
    updatedTemplate = updatedTemplate.replace(pattern, ' ');

    // Clean up extra spaces
    updatedTemplate = updatedTemplate.replace(/\s+/g, ' ').trim();

    this.selectedTemplate.structural_template = updatedTemplate;

    // Reparse template
    this.tokens = this.parser.parseTemplate(this.selectedTemplate.structural_template);
    this.collected = this.parser.collectElements(this.tokens);

    // Update display
    this.updateAll();

    // Close modal
    this.closeDeleteTextModal();
  }

  /* =========================
   * UNIFIED ADD ELEMENT MODAL
   * ========================= */

  /**
   * Opens the unified Add Element modal
   */
  openAddElementModal(): void {
    if (!this.selectedTemplate) return;
    
    // Reset type selection
    this.addElementType = '';
    
    // Reset all forms
    this.newComponent = {
      label: '',
      text: '',
      description: '',
      examplesText: '',
      required: false,
      allowCustom: true
    };
    
    this.newChoice = {
      optionsText: '',
      required: false
    };
    
    this.newText = {
      content: ''
    };
    
    this.addElementModalVisible = true;
  }

  /**
   * Closes the unified Add Element modal
   */
  closeAddElementModal(): void {
    this.addElementModalVisible = false;
    this.addElementType = '';
  }

  /**
   * Handles element type change in Add modal
   */
  onAddElementTypeChange(): void {
    // Reset forms when type changes
    this.newComponent = {
      label: '',
      text: '',
      description: '',
      examplesText: '',
      required: false,
      allowCustom: true
    };
    
    this.newChoice = {
      optionsText: '',
      required: false
    };
    
    this.newText = {
      content: ''
    };
  }

  /**
   * Checks if current element can be saved
   */
  canSaveAddElement(): boolean {
    if (this.addElementType === 'component') {
      return !!this.newComponent.label;
    } else if (this.addElementType === 'choice') {
      return this.isValidChoiceOptions();
    } else if (this.addElementType === 'text') {
      return !!this.newText.content?.trim();
    }
    return false;
  }

  /**
   * Saves the selected element type
   */
  saveAddElement(): void {
    if (this.addElementType === 'component') {
      this.saveNewComponent();
    } else if (this.addElementType === 'choice') {
      this.saveNewChoice();
    } else if (this.addElementType === 'text') {
      this.saveNewText();
    }
    
    this.closeAddElementModal();
  }

  /* =========================
   * UNIFIED DELETE ELEMENT MODAL
   * ========================= */

  /**
   * Opens the unified Delete Element modal
   */
  openDeleteElementModal(): void {
    if (!this.selectedTemplate) return;
    
    // Reset type selection
    this.deleteElementType = '';
    
    // Reset selections
    this.componentToDelete = '';
    this.choiceToDelete = '';
    this.textToDelete = '';
    
    this.deleteElementModalVisible = true;
  }

  /**
   * Closes the unified Delete Element modal
   */
  closeDeleteElementModal(): void {
    this.deleteElementModalVisible = false;
    this.deleteElementType = '';
    this.componentToDelete = '';
    this.choiceToDelete = '';
    this.textToDelete = '';
    this.availableComponentsForDeletion = [];
    this.availableChoicesForDeletion = [];
    this.availableTextsForDeletion = [];
  }

  /**
   * Handles element type change in Delete modal
   */
  onDeleteElementTypeChange(): void {
    // Reset selections
    this.componentToDelete = '';
    this.choiceToDelete = '';
    this.textToDelete = '';
    
    // Load available items based on selected type
    if (this.deleteElementType === 'component') {
      this.availableComponentsForDeletion = this.collected.components.map(c => c.name);
    } else if (this.deleteElementType === 'choice') {
      this.availableChoicesForDeletion = this.collected.choices.map(c => ({
        id: c.id!,
        displayText: c.options!.join('/'),
        options: c.options!
      }));
    } else if (this.deleteElementType === 'text') {
      const textFragments: string[] = [];
      for (const token of this.tokens) {
        if (token.type === 'text' && token.value) {
          const trimmed = token.value.trim();
          const wordCount = trimmed.split(/\s+/).length;
          if (wordCount >= 2) {
            textFragments.push(trimmed);
          }
        }
      }
      this.availableTextsForDeletion = textFragments;
    }
  }

  /**
   * Checks if an element can be deleted
   */
  canDeleteElement(): boolean {
    if (this.deleteElementType === 'component') {
      return !!this.componentToDelete && this.availableComponentsForDeletion.length > 0;
    } else if (this.deleteElementType === 'choice') {
      return !!this.choiceToDelete && this.availableChoicesForDeletion.length > 0;
    } else if (this.deleteElementType === 'text') {
      return !!this.textToDelete && this.availableTextsForDeletion.length > 0;
    }
    return false;
  }

  /**
   * Confirms deletion of selected element
   */
  confirmDeleteElement(): void {
    if (this.deleteElementType === 'component') {
      this.confirmDeleteComponent();
    } else if (this.deleteElementType === 'choice') {
      this.confirmDeleteChoice();
    } else if (this.deleteElementType === 'text') {
      this.confirmDeleteText();
    }
    
    this.closeDeleteElementModal();
  }

  /* =========================
   * REORDER ELEMENTS MODAL
   * ========================= */

  /**
   * Opens the reorder modal
   */
  openReorderModal(): void {
    if (!this.selectedTemplate) return;
    
    // Create a working copy of tokens for reordering
    this.reorderableTokens = JSON.parse(JSON.stringify(this.tokens));
    
    this.reorderModalVisible = true;
  }

  /**
   * Closes the reorder modal
   */
  closeReorderModal(): void {
    this.reorderModalVisible = false;
    this.reorderableTokens = [];
  }

  /**
   * Moves an element up in the order
   */
  moveElementUp(index: number): void {
    if (index <= 0 || index >= this.reorderableTokens.length) return;
    
    // Swap with previous element
    const temp = this.reorderableTokens[index];
    this.reorderableTokens[index] = this.reorderableTokens[index - 1];
    this.reorderableTokens[index - 1] = temp;
  }

  /**
   * Moves an element down in the order
   */
  moveElementDown(index: number): void {
    if (index < 0 || index >= this.reorderableTokens.length - 1) return;
    
    // Swap with next element
    const temp = this.reorderableTokens[index];
    this.reorderableTokens[index] = this.reorderableTokens[index + 1];
    this.reorderableTokens[index + 1] = temp;
  }

  /**
   * Gets the badge text for element type
   */
  getElementTypeBadge(type: string): string {
    switch (type) {
      case 'component': return 'Component';
      case 'choice': return 'Choice';
      case 'text': return 'Text';
      case 'optional': return 'Optional';
      default: return 'Unknown';
    }
  }

  /**
   * Gets display text for an element
   */
  getElementDisplayText(token: Token): string {
    if (token.type === 'component') {
      return `<${token.name}>`;
    } else if (token.type === 'choice') {
      return `[${token.options?.join('/')}]`;
    } else if (token.type === 'text') {
      const text = (token.value || '').trim();
      return text.length > 50 ? text.substring(0, 50) + '...' : text;
    } else if (token.type === 'optional') {
      return `{optional block}`;
    }
    return 'Unknown';
  }

  /**
   * Saves the new order and rebuilds the template
   */
  saveReorder(): void {
    if (!this.selectedTemplate) return;
    
    // Update the main tokens array
    this.tokens = this.reorderableTokens;
    
    // Rebuild the structural template string from tokens
    this.selectedTemplate.structural_template = this.rebuildTemplateFromTokens(this.tokens);
    
    // Recollect elements
    this.collected = this.parser.collectElements(this.tokens);
    
    // Update display
    this.updateAll();
    
    // Close modal
    this.closeReorderModal();
  }

  /**
   * Rebuilds the structural template string from tokens
   */
  private rebuildTemplateFromTokens(tokens: Token[]): string {
    const parts: string[] = [];
    
    for (const token of tokens) {
      if (token.type === 'text') {
        parts.push(token.value || '');
      } else if (token.type === 'component') {
        const marker = token.required ? '*' : '';
        parts.push(`${marker}<${token.name}>`);
      } else if (token.type === 'choice') {
        const marker = token.required ? '*' : '';
        parts.push(`${marker}[${token.options?.join('/')}]`);
      } else if (token.type === 'optional') {
        // Recursively rebuild optional content
        const innerContent = this.rebuildTemplateFromTokens(token.children || []);
        parts.push(`{${innerContent}}`);
      }
    }
    
    return parts.join(' ').replace(/\s+/g, ' ').trim();
  }

  /* =========================
   * SUGGEST TEMPLATE MODAL
   * ========================= */

  /**
   * Opens the suggest template modal
   */
  openSuggestTemplateModal(): void {
    if (!this.currentOriginalSentence) return;
    
    // Reset state
    this.suggestMode = '';
    this.suggestingTemplate = false;
    this.suggestError = null;
    
    this.suggestTemplateModalVisible = true;
  }

  /**
   * Closes the suggest template modal
   */
  closeSuggestTemplateModal(): void {
    this.suggestTemplateModalVisible = false;
    this.suggestMode = '';
    this.suggestingTemplate = false;
    this.suggestError = null;
  }

  /**
   * Executes the template suggestion based on selected mode
   */
  async executeSuggestTemplate(): Promise<void> {
    if (!this.suggestMode || !this.currentOriginalSentence) return;

    this.suggestingTemplate = true;
    this.suggestError = null;

    try {
      const response = await firstValueFrom(
        this.crd13Api.adaptAttestationTemplate(this.currentOriginalSentence)
      );

      // Apply the suggested/created template
      this.applySuggestedTemplateFromModal(response);
      
      // Show success message
      const action = response.created_new ? 'created' : 'identified';
      const message = `Template ${action} successfully`;
      
      // Close modal
      this.closeSuggestTemplateModal();
      
      // Show success notification
      this.showToast(message, 'success');

    } catch (e: any) {
      this.suggestError = e?.message || 'Failed to suggest template. Please try again.';
      console.error('Error suggesting template:', e);
    } finally {
      this.suggestingTemplate = false;
    }
  }

  /**
   * Applies the suggested template from the modal
   */
  private applySuggestedTemplateFromModal(res: IdentifyTemplateResponse): void {
    const suggested = res?.template;
    if (!suggested?.id) {
      this.suggestError = 'Template suggestion returned no template.';
      return;
    }

    // If API created a new template, merge it into allTemplates
    if (res.created_new) {
      const exists = this.allTemplates.some(t => t.id === suggested.id);
      if (!exists) {
        // Mark as custom type
        suggested.type = 'custom';
        this.allTemplates = [...this.allTemplates, suggested];
        
        // Register as custom created template
        this.customTemplateIds.add(suggested.id);
        this.templateMetadata.set(suggested.id, {
          source: 'created',
          addedAt: new Date().toISOString(),
          usedInRequirements: []
        });
        
        this.buildFilterOptions();
      }
    }

    // 1) Sync sidebar dropdowns to suggested template
    this.selectedModality = suggested.modality || 'any';
    this.selectedFunction = suggested.communicative_function || 'any';

    // 2) Re-filter list so sidebar shows the right options/count
    this.applyFilters();

    // 3) Select the actual template instance from allTemplates (preferred)
    const templateFromStore =
      this.allTemplates.find(t => t.id === suggested.id) || suggested;

    this.selectTemplate(templateFromStore);

    // 4) Fill state from suggested components and mark them as edited
    // IMPORTANT: do this AFTER selectTemplate(), because selectTemplate() calls resetState()
    for (const c of Object.values(suggested.components || {})) {
      if (!c?.label) continue;

      this.state.values[c.label] = String(c.text ?? '');
      this.editedComponents.add(c.label);
    }

    // 5) Now force full recompute (preview + generatedSentence + validation)
    this.updateAll();

    // Keep the original sentence for display
    if (res.sentence?.trim()) {
      this.currentOriginalSentence = res.sentence.trim();
    }

    // Close popover if open
    this.closePopover();
  }

}
