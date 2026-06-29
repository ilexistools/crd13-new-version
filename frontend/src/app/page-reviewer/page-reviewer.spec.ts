import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PageReviewer } from './page-reviewer';

describe('PageReviewer', () => {
  let component: PageReviewer;
  let fixture: ComponentFixture<PageReviewer>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [PageReviewer]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PageReviewer);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
