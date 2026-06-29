import { ComponentFixture, TestBed } from '@angular/core/testing';

import { WidgetSegmenter } from './widget-segmenter';

describe('WidgetSegmenter', () => {
  let component: WidgetSegmenter;
  let fixture: ComponentFixture<WidgetSegmenter>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WidgetSegmenter]
    })
    .compileComponents();

    fixture = TestBed.createComponent(WidgetSegmenter);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
