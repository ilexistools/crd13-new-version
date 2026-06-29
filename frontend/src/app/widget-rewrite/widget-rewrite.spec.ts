import { ComponentFixture, TestBed } from '@angular/core/testing';

import { WidgetRewrite } from './widget-rewrite';

describe('WidgetRewrite', () => {
  let component: WidgetRewrite;
  let fixture: ComponentFixture<WidgetRewrite>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WidgetRewrite]
    })
    .compileComponents();

    fixture = TestBed.createComponent(WidgetRewrite);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
