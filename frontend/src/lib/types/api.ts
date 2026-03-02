export interface ApiError {
  detail: string | { msg: string }[];
  status_code?: number;
}
