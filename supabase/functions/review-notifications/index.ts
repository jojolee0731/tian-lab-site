// Version confirmed against https://registry.npmjs.org/nodemailer/10.0.10.
// SMTP options/verify semantics: https://nodemailer.com/smtp
import nodemailer from 'npm:nodemailer@10.0.10';
import { connect } from 'node:tls';
import { createHandler, createSmtpAdapter } from './handler.mjs';

const env = (name: string) => Deno.env.get(name);
const smtp = createSmtpAdapter({ env, createTransport: nodemailer.createTransport, connectTls: connect });
Deno.serve(createHandler({ env, ...smtp }));
