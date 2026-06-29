import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { MatIconModule } from '@angular/material/icon';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { PageReviewer } from './page-reviewer/page-reviewer';
import { WidgetRewrite } from './widget-rewrite/widget-rewrite';
import { WidgetSegmenterComponent } from './widget-segmenter/widget-segmenter';

@NgModule({
  declarations: [
    AppComponent,
    PageReviewer,
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    BrowserAnimationsModule,
    CommonModule,
    FormsModule,
    HttpClientModule,
    MatIconModule,
    WidgetRewrite,
    WidgetSegmenterComponent,
  ],
  bootstrap: [AppComponent],
})
export class AppModule { }
