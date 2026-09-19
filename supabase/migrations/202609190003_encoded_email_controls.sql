-- Keep database approval validation aligned with public email/mailto export validation.
-- Only the two encoded-control regexes change; grants and security attributes are retained.
create or replace function member_portal.validate_payload(payload jsonb, owner_id text) returns void
language plpgsql security definer set search_path='' as $$
declare k text; v jsonb; e jsonb; z jsonb; field text; lim integer; ids text[]:=array[]::text[];
begin
 if payload is null or jsonb_typeof(payload)<>'object' or octet_length(payload::text)>524288 then raise exception using errcode='22023',message='invalid_payload'; end if;
 for k,v in select * from jsonb_each(payload) loop
  if not k=any(array['bio','bio_en','interests','interests_en','education','education_en','public_email','avatar_path','links','projects','papers']) then raise exception using errcode='22023',message='unknown_field:'||k; end if;
  if not k=any(array['links','projects','papers']) then perform member_portal.check_text(v,case when k='public_email' then 254 when k='avatar_path' then 150 else 3000 end,k); end if;
 end loop;
 if coalesce(payload->>'public_email','')<>'' and (payload->>'public_email' !~ '^[A-Za-z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$' or payload->>'public_email' ~* '%(0[0-9a-f]|1[0-9a-f]|7f)') then raise exception using errcode='22023',message='invalid_public_email'; end if;
 perform member_portal.check_path(payload->>'avatar_path',owner_id);
 foreach field in array array['links','projects','papers'] loop
  if not payload?field then continue; end if;
  if jsonb_typeof(payload->field)<>'array' then raise exception using errcode='22023',message='invalid_array:'||field; end if;
  lim:=case field when 'links' then 5 when 'projects' then 3 else 30 end;
  if jsonb_array_length(payload->field)>lim then raise exception using errcode='22023',message='too_many:'||field; end if;
  for e in select * from jsonb_array_elements(payload->field) loop
   if jsonb_typeof(e)<>'object' then raise exception using errcode='22023',message='invalid_item:'||field; end if;
   for k,v in select * from jsonb_each(e) loop
    if (field='links' and not k=any(array['label','url'])) or (field='projects' and not k=any(array['id','title','title_en','question','question_en','approach','approach_en','contribution','contribution_en','progress','progress_en','image_path','image_caption','image_caption_en','image_source'])) or (field='papers' and not k=any(array['doi','title','authors','journal','year','context','contribution','contribution_en'])) then raise exception using errcode='22023',message='unknown_item_field:'||k; end if;
    if field='papers' and k='year' then
     if jsonb_typeof(v) not in ('string','number') or v#>>'{}' !~ '^(18|19|20)[0-9]{2}$' then raise exception using errcode='22023',message='invalid_paper_year'; end if;
    else
     lim:=case when field='papers' and k='title' then 1000 when k=any(array['title','title_en','journal','label']) then 200 when k='authors' then 2000 when k='doi' then 255 when k='url' then 2048 when k=any(array['image_path','id','context']) then 150 else 3000 end;
     perform member_portal.check_text(v,lim,field||'.'||k);
    end if;
   end loop;
   if field='links' then
    if coalesce(e->>'label','')='' or coalesce(e->>'url','')='' or (e->>'url' !~ '^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]{1,5})?([/?#][^[:space:]<>]*)?$' and e->>'url' !~ '^mailto:[A-Za-z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$') then raise exception using errcode='22023',message='invalid_external_link'; end if;
    if e->>'url' ~* '^mailto:' and e->>'url' ~* '%(0[0-9a-f]|1[0-9a-f]|7f)' then raise exception using errcode='22023',message='invalid_external_link'; end if;
   elsif field='projects' then
    if coalesce(e->>'id','') !~ '^[A-Za-z0-9_-]{1,80}$' or coalesce(e->>'title','')='' or e->>'id'=any(ids) then raise exception using errcode='22023',message='invalid_project_identity'; end if;
    ids:=array_append(ids,e->>'id'); perform member_portal.check_path(e->>'image_path',owner_id);
    if coalesce(e->>'image_path','')<>'' and ((btrim(coalesce(e->>'image_caption',''))='' and btrim(coalesce(e->>'image_caption_en',''))='') or btrim(coalesce(e->>'image_source',''))='') then raise exception using errcode='22023',message='project_image_caption_and_source_required'; end if;
   else
    if coalesce(e->>'title','')='' or coalesce(e->>'context','') not in ('in_lab','before_lab') then raise exception using errcode='22023',message='invalid_paper_identity'; end if;
    if coalesce(e->>'doi','')<>'' and (e->>'doi' !~ '^10\.[0-9]{4,9}/[^[:space:]<>]{1,240}$' or e->>'doi' ~ '[?#"'']' or position(chr(92) in e->>'doi')>0) then raise exception using errcode='22023',message='invalid_doi'; end if;
   end if;
  end loop;
 end loop;
end $$;
