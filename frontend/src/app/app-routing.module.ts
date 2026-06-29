import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { PageReviewer } from './page-reviewer/page-reviewer';

const routes: Routes = [
  { path: '', component: PageReviewer },
  { path: 'editor', component: PageReviewer },
  { path: '**', redirectTo: '' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule { }
