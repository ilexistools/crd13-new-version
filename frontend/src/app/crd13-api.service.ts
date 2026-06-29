import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable, switchMap } from 'rxjs';

import { TemplateComponent, TemplateItem, TemplatesRoot } from './models/template.models';
import { Provision, RewriteResult } from './widget-rewrite/widget-rewrite';

type Triple = { subject: string; predicate: string; object: string };

type BackendEnvelope<T> = {
  output?: T;
};

type BackendToolResult<T> = {
  input?: unknown;
  output?: BackendToolResult<T>;
  results?: T;
};

type TemplateAdaptationResult = {
  input_attestation?: string;
  template_adaptation_decision?: string;
  selected_template?: Partial<TemplateItem>;
  adapted_attestation?: string | null;
  component_mapping?: Array<{
    component_name: string;
    value?: string;
    source_text?: string;
    status?: string;
    preservation_note?: string;
  }>;
  template_selection_rationale?: string;
  confidence?: number;
  final_assessment?: string;
};

type AnalysisResult = {
  attestation_sentence?: string;
  overall_decision?: string;
  support_level?: string;
  final_assessment?: string;
};

export type ComplianceAnalysisResult = {
  attestation?: string;
  overall_assessment?: {
    compliance?: string;
    summary?: string;
  };
  principle_assessments?: Array<{
    principle?: string;
    principle_name?: string;
    compliance?: string;
    relevant_text_fragment?: string;
    issue_identified?: string;
    explanation?: string;
  }>;
  identified_elements?: Record<string, string[]>;
  missing_information?: string[];
  final_assessment?: string;
};

type RewriteBackendResult = {
  decision?: string;
  rewritten?: string;
  rewrite_notes?: string[];
};

@Injectable({ providedIn: 'root' })
export class Crd13ApiService {
  private readonly undefinedTemplateId = 'UND-8f2c3a1b-5d7e-4d2b-9f6a-0b7f3d2b1a9c';
  private readonly baseUrl = 'http://127.0.0.1:8000';

  constructor(private http: HttpClient) {}

  getTemplates(): Observable<TemplatesRoot> {
    return this.http.get<TemplatesRoot>(`${this.baseUrl}/templates`).pipe(
      map(root => {
        const items = (root?.items || []).map(item => this.normalizeTemplate(item));
        if (!items.some(item => item.id === this.undefinedTemplateId)) {
          items.unshift(this.undefinedTemplate());
        }

        return {
          version: root?.version || 'attestation-1.0',
          items,
        };
      })
    );
  }

  extractPdfText(file: File): Observable<string> {
    const formData = new FormData();
    formData.append('file', file, file.name);

    return this.http.post<any>(`${this.baseUrl}/extract_pdf_text`, formData).pipe(
      map(res => {
        const text = String(res?.full_text || '').trim();
        if (text) return text;
        if (!Array.isArray(res?.pages)) return '';
        return res.pages
          .map((page: any) => String(page?.text || page || '').trim())
          .filter(Boolean)
          .join('\n');
      })
    );
  }

  identifyCommodities(text: string): Observable<string[]> {
    return this.postTool<string[]>('/identify_commodities', { text }).pipe(
      map(result => this.asStringArray(this.unwrapResults(result)))
    );
  }

  unitize(text: string): Observable<string[]> {
    return this.postTool<string[]>('/unitize', { text }).pipe(
      map(result => this.asStringArray(this.unwrapResults(result)))
    );
  }

  analyzeCompliance(attestation: string): Observable<ComplianceAnalysisResult> {
    return this.postTool<ComplianceAnalysisResult>('/analyze_compliance', { attestation }).pipe(
      map(result => (this.unwrapResults(result) || result || {}) as ComplianceAnalysisResult)
    );
  }

  generateTriples(text: string): Observable<Triple[]> {
    return this.postTool<Triple[]>('/generate_triples', { text }).pipe(
      map(result => (this.unwrapResults(result) || []) as Triple[])
    );
  }

  searchProvisions(text: string, commodities: string[]): Observable<Provision[]> {
    return this.postTool<any[]>('/search_provisions', { text, commodities }).pipe(
      map(result => {
        const rows = this.unwrapResults(result);
        return Array.isArray(rows) ? rows.map(row => this.toProvision(row)) : [];
      })
    );
  }

  rewriteAttestation(sentence: string, provisions: Provision[]): Observable<RewriteResult> {
    const backendProvisions = provisions.map(provision => this.fromProvision(provision));

    return this.postTool<AnalysisResult>('/analyze_attestation', {
      attestation: sentence,
      provisions: backendProvisions,
    }).pipe(
      map(result => this.unwrapResults(result) || result),
      switchMap(analysisResult =>
        this.postTool<RewriteBackendResult>('/rewrite_attestation', { analysis_result: analysisResult }).pipe(
          map(rewriteResult => {
            const rewrite = this.unwrapResults(rewriteResult) || rewriteResult || {};
            const analysis = (analysisResult || {}) as AnalysisResult;
            return {
              original: sentence,
              text: String((rewrite as RewriteBackendResult).rewritten || sentence),
              modality: String(analysis.overall_decision || ''),
              communicative_function: String(analysis.support_level || ''),
              template: String((rewrite as RewriteBackendResult).decision || 'new-backend rewrite'),
              commodity: backendProvisions.flatMap(item => item.commodities || []),
            };
          })
        )
      )
    );
  }

  adaptAttestationTemplate(attestation: string): Observable<{
    sentence: string;
    template: TemplateItem;
    created_new: boolean;
  }> {
    return this.postTool<TemplateAdaptationResult>('/adapt_attestation_template', { attestation }).pipe(
      map(result => {
        const adaptation = (this.unwrapResults(result) || result || {}) as TemplateAdaptationResult;
        return {
          sentence: adaptation.input_attestation || attestation,
          template: this.templateFromAdaptation(adaptation, attestation),
          created_new: false,
        };
      })
    );
  }

  normalizeTemplateForFrontend(item: unknown): TemplateItem {
    return this.normalizeTemplate(item);
  }

  private postTool<T>(path: string, input: Record<string, unknown>): Observable<T> {
    return this.http.post<BackendEnvelope<T>>(`${this.baseUrl}${path}`, { input }).pipe(
      map(response => response?.output as T)
    );
  }

  private unwrapResults<T>(value: any): T | undefined {
    if (value?.results !== undefined) return value.results as T;
    if (value?.output?.results !== undefined) return value.output.results as T;
    if (value?.output?.output?.results !== undefined) return value.output.output.results as T;
    return value as T;
  }

  private asStringArray(value: unknown): string[] {
    return Array.isArray(value)
      ? value.map(item => String(item || '').trim()).filter(Boolean)
      : [];
  }

  private normalizeTemplate(item: any): TemplateItem {
    const components: Record<string, TemplateComponent> = {};
    Object.entries(item?.components || {}).forEach(([key, raw]: [string, any], index) => {
      const label = String(raw?.label || key).trim();
      components[String(index + 1)] = {
        label,
        text: String(raw?.text || raw?.value || ''),
        required: Boolean(raw?.required),
        description: String(raw?.description || ''),
        examples: Array.isArray(raw?.examples) ? raw.examples.map((ex: any) => String(ex)) : [],
        allow_custom: raw?.allow_custom !== false,
      };
    });

    return {
      id: String(item?.id || `TPL-${Date.now()}`),
      type: String(item?.type || 'default'),
      category: String(item?.category || ''),
      commodities: Array.isArray(item?.commodities) ? item.commodities : undefined,
      modality: String(item?.modality || item?.regulatory_modality || ''),
      communicative_function: String(item?.communicative_function || item?.attestation_function || ''),
      representative_example: String(item?.representative_example || ''),
      structural_template: this.normalizeTemplateChoices(String(item?.structural_template || '*<sentence>')),
      components,
    };
  }

  private undefinedTemplate(): TemplateItem {
    return {
      id: this.undefinedTemplateId,
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

  private normalizeTemplateChoices(template: string): string {
    return template.replace(/(^|[\s,{])([A-Za-z]+(?:\/[A-Za-z]+)+)(?=($|[\s,}.]))/g, '$1[$2]');
  }

  private templateFromAdaptation(adaptation: TemplateAdaptationResult, attestation: string): TemplateItem {
    const selected = this.normalizeTemplate({
      ...adaptation.selected_template,
      representative_example: adaptation.adapted_attestation || attestation,
    });

    for (const mapping of adaptation.component_mapping || []) {
      const component = Object.values(selected.components).find(c => c.label === mapping.component_name);
      if (component) {
        component.text = String(mapping.value || mapping.source_text || '');
        continue;
      }

      const nextKey = String(Object.keys(selected.components).length + 1);
      selected.components[nextKey] = {
        label: mapping.component_name,
        text: String(mapping.value || mapping.source_text || ''),
        required: mapping.status !== 'omitted_optional' && mapping.status !== 'not_applicable',
        description: String(mapping.preservation_note || ''),
        examples: [],
        allow_custom: true,
      };
    }

    if (!Object.keys(selected.components).length) {
      selected.id = selected.id || 'ADAPT-FALLBACK';
      selected.structural_template = '*<sentence>';
      selected.components = {
        '1': {
          label: 'sentence',
          text: adaptation.adapted_attestation || attestation,
          required: true,
          description: 'Fallback sentence from template adaptation.',
          examples: [attestation],
          allow_custom: true,
        },
      };
    }

    return selected;
  }

  private toProvision(row: any): Provision {
    const text = String(row?.sentence || row?.raw_json?.sentence || '');
    const metadata = row?.raw_json || {};
    const relevance = typeof row?.relevance === 'number' ? row.relevance / 100 : 0;

    return {
      rank: Number(row?.rank || 0),
      similarity: relevance,
      doc: {
        text,
        metadata: {
          commodities: Array.isArray(row?.commodities) ? row.commodities : [],
          process: metadata.process || row?.function || '',
          subject: metadata.subject || row?.category || '',
          sentence: text,
          section: String(row?.section_title || ''),
          section_title: String(row?.section_title || ''),
          page: row?.page_start ?? row?.page_end ?? undefined,
          doc_id: String(row?.document_id || row?.id || ''),
          total_pages: undefined,
          type: String(row?.type || 'provision'),
          doc_title: String(row?.document_id || 'CRD13 provision'),
        },
      },
    };
  }

  private fromProvision(provision: Provision): any {
    return {
      id: provision.rank,
      sentence: provision.doc.text,
      commodities: provision.doc.metadata.commodities || [],
      type: provision.doc.metadata.type,
      section_title: provision.doc.metadata.section_title,
      page: provision.doc.metadata.page,
      document_id: provision.doc.metadata.doc_id,
      category: provision.doc.metadata.subject,
      function: provision.doc.metadata.process,
      relevance: Math.round((provision.similarity || 0) * 100),
    };
  }
}
