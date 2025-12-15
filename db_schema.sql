--
-- PostgreSQL database dump
--

\restrict XggjwLegZAvbDbLLwt7vrhcn7ahJxZsqyLz8Q5KJzv2OTL4QwJCY52ARqvjluoB

-- Dumped from database version 17.7
-- Dumped by pg_dump version 17.7

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: set_timestamp_strategy_universe(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_timestamp_strategy_universe() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_timestamp_strategy_universe() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_state; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.account_state (
    id bigint DEFAULT 1 NOT NULL,
    equity numeric(20,6) NOT NULL,
    free_cash numeric(20,6) NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    currency text DEFAULT 'RUB'::text,
    used_margin numeric(20,6) DEFAULT 0 NOT NULL
);


ALTER TABLE public.account_state OWNER TO postgres;

--
-- Name: backtest_runs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.backtest_runs (
    id integer NOT NULL,
    optimization_id integer,
    strategy_id integer NOT NULL,
    symbol_id integer NOT NULL,
    timeframe_table character varying(50) NOT NULL,
    window_start timestamp without time zone NOT NULL,
    window_end timestamp without time zone NOT NULL,
    trial_number integer,
    is_best smallint DEFAULT 0 NOT NULL,
    params_json text NOT NULL,
    cagr double precision,
    sharpe double precision,
    max_dd double precision,
    profit_factor double precision,
    trades_count integer,
    target_metric_value double precision,
    trades_json text,
    indicators_json text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.backtest_runs OWNER TO postgres;

--
-- Name: backtest_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.backtest_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.backtest_runs_id_seq OWNER TO postgres;

--
-- Name: backtest_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.backtest_runs_id_seq OWNED BY public.backtest_runs.id;


--
-- Name: bar_state; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bar_state (
    id bigint NOT NULL,
    service_name text NOT NULL,
    timeframe text NOT NULL,
    last_bar_timestamp timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bar_state OWNER TO postgres;

--
-- Name: bar_state_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bar_state_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bar_state_id_seq OWNER TO postgres;

--
-- Name: bar_state_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bar_state_id_seq OWNED BY public.bar_state.id;


--
-- Name: candles_15m_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_15m_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_15m_id_seq OWNER TO postgres;

--
-- Name: candles_15m; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_15m (
    id integer DEFAULT nextval('public.candles_15m_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL,
    is_gap boolean DEFAULT false NOT NULL,
    gap_dir text
);


ALTER TABLE public.candles_15m OWNER TO postgres;

--
-- Name: candles_1d_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_1d_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_1d_id_seq OWNER TO postgres;

--
-- Name: candles_1d; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1d (
    id integer DEFAULT nextval('public.candles_1d_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL,
    is_gap boolean DEFAULT false NOT NULL,
    gap_dir text
);


ALTER TABLE public.candles_1d OWNER TO postgres;

--
-- Name: candles_1h_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_1h_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_1h_id_seq OWNER TO postgres;

--
-- Name: candles_1h; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1h (
    id integer DEFAULT nextval('public.candles_1h_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL,
    is_gap boolean DEFAULT false NOT NULL,
    gap_dir text
);


ALTER TABLE public.candles_1h OWNER TO postgres;

--
-- Name: candles_1m_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_1m_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_1m_id_seq OWNER TO postgres;

--
-- Name: candles_1m; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_1m (
    id integer DEFAULT nextval('public.candles_1m_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL
);


ALTER TABLE public.candles_1m OWNER TO postgres;

--
-- Name: candles_30m_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_30m_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_30m_id_seq OWNER TO postgres;

--
-- Name: candles_30m; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_30m (
    id integer DEFAULT nextval('public.candles_30m_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL,
    is_gap boolean DEFAULT false NOT NULL,
    gap_dir text
);


ALTER TABLE public.candles_30m OWNER TO postgres;

--
-- Name: candles_4h_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_4h_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_4h_id_seq OWNER TO postgres;

--
-- Name: candles_4h; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_4h (
    id integer DEFAULT nextval('public.candles_4h_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL,
    is_gap boolean DEFAULT false NOT NULL,
    gap_dir text
);


ALTER TABLE public.candles_4h OWNER TO postgres;

--
-- Name: candles_5m_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.candles_5m_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.candles_5m_id_seq OWNER TO postgres;

--
-- Name: candles_5m; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.candles_5m (
    id integer DEFAULT nextval('public.candles_5m_id_seq'::regclass) NOT NULL,
    symbol_id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    open double precision NOT NULL,
    high double precision NOT NULL,
    low double precision NOT NULL,
    close double precision NOT NULL,
    volume bigint NOT NULL,
    is_gap boolean DEFAULT false NOT NULL,
    gap_dir text
);


ALTER TABLE public.candles_5m OWNER TO postgres;

--
-- Name: datafeed_state; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.datafeed_state (
    id integer DEFAULT 1 NOT NULL,
    last_1m_timestamp timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.datafeed_state OWNER TO postgres;

--
-- Name: live_errors; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.live_errors (
    id bigint NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    source text NOT NULL,
    severity text NOT NULL,
    strategy_universe_id bigint,
    symbol text,
    timeframe text,
    message text NOT NULL,
    details_json jsonb
);


ALTER TABLE public.live_errors OWNER TO postgres;

--
-- Name: live_errors_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.live_errors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.live_errors_id_seq OWNER TO postgres;

--
-- Name: live_errors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.live_errors_id_seq OWNED BY public.live_errors.id;


--
-- Name: live_orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.live_orders (
    id bigint NOT NULL,
    live_signal_id bigint,
    strategy_universe_id bigint NOT NULL,
    symbol text NOT NULL,
    timeframe text,
    side text NOT NULL,
    quantity numeric(20,6) NOT NULL,
    price numeric(20,6),
    order_type text NOT NULL,
    time_in_force text,
    status text NOT NULL,
    broker_order_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    broker_payload jsonb
);


ALTER TABLE public.live_orders OWNER TO postgres;

--
-- Name: live_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.live_orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.live_orders_id_seq OWNER TO postgres;

--
-- Name: live_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.live_orders_id_seq OWNED BY public.live_orders.id;


--
-- Name: live_positions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.live_positions (
    id bigint NOT NULL,
    strategy_universe_id bigint NOT NULL,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    direction text NOT NULL,
    quantity numeric(20,6) NOT NULL,
    avg_price numeric(20,6) NOT NULL,
    realized_pnl numeric(20,6) DEFAULT 0 NOT NULL,
    unrealized_pnl numeric(20,6) DEFAULT 0 NOT NULL,
    drawdown_fraction double precision DEFAULT 0 NOT NULL,
    gap_mode boolean DEFAULT false NOT NULL,
    manual_block_until timestamp with time zone,
    opened_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_price numeric(20,6)
);


ALTER TABLE public.live_positions OWNER TO postgres;

--
-- Name: live_positions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.live_positions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.live_positions_id_seq OWNER TO postgres;

--
-- Name: live_positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.live_positions_id_seq OWNED BY public.live_positions.id;


--
-- Name: live_signals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.live_signals (
    id bigint NOT NULL,
    strategy_universe_id bigint NOT NULL,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    bar_timestamp timestamp with time zone NOT NULL,
    signal_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    signal_type text NOT NULL,
    signal_source text DEFAULT 'strategy'::text NOT NULL,
    signal_json jsonb NOT NULL,
    gap_flag boolean DEFAULT false NOT NULL,
    processed boolean DEFAULT false NOT NULL,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.live_signals OWNER TO postgres;

--
-- Name: live_signals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.live_signals_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.live_signals_id_seq OWNER TO postgres;

--
-- Name: live_signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.live_signals_id_seq OWNED BY public.live_signals.id;


--
-- Name: live_trades; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.live_trades (
    id bigint NOT NULL,
    live_order_id bigint,
    strategy_universe_id bigint NOT NULL,
    symbol text NOT NULL,
    timeframe text,
    side text NOT NULL,
    quantity numeric(20,6) NOT NULL,
    price numeric(20,6) NOT NULL,
    fee numeric(20,6) DEFAULT 0 NOT NULL,
    executed_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    trade_type text
);


ALTER TABLE public.live_trades OWNER TO postgres;

--
-- Name: live_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.live_trades_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.live_trades_id_seq OWNER TO postgres;

--
-- Name: live_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.live_trades_id_seq OWNED BY public.live_trades.id;


--
-- Name: lot_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lot_history (
    id integer NOT NULL,
    symbol_id integer NOT NULL,
    lot_size integer NOT NULL,
    change_date timestamp without time zone NOT NULL,
    comment character varying(255) DEFAULT ''::character varying
);


ALTER TABLE public.lot_history OWNER TO postgres;

--
-- Name: lot_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lot_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lot_history_id_seq OWNER TO postgres;

--
-- Name: lot_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lot_history_id_seq OWNED BY public.lot_history.id;


--
-- Name: optimization_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.optimization_sessions (
    id integer NOT NULL,
    strategy_id integer NOT NULL,
    symbol_id integer NOT NULL,
    timeframe_table character varying(50) NOT NULL,
    window_start timestamp without time zone NOT NULL,
    window_end timestamp without time zone NOT NULL,
    study_name character varying(100),
    storage_url character varying(255),
    target_metric character varying(50) NOT NULL,
    direction character varying DEFAULT 'maximize'::character varying NOT NULL,
    n_trials integer NOT NULL,
    status character varying DEFAULT 'created'::character varying NOT NULL,
    best_value double precision,
    best_params text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    finished_at timestamp without time zone
);


ALTER TABLE public.optimization_sessions OWNER TO postgres;

--
-- Name: optimization_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.optimization_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.optimization_sessions_id_seq OWNER TO postgres;

--
-- Name: optimization_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.optimization_sessions_id_seq OWNED BY public.optimization_sessions.id;


--
-- Name: service_status; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.service_status (
    service_name text NOT NULL,
    last_heartbeat timestamp with time zone DEFAULT now() NOT NULL,
    status text DEFAULT 'ok'::text NOT NULL,
    details_json jsonb
);


ALTER TABLE public.service_status OWNER TO postgres;

--
-- Name: strategy_catalog; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.strategy_catalog (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text NOT NULL,
    py_module character varying(200) NOT NULL,
    py_class character varying(100) NOT NULL,
    enabled smallint DEFAULT 1 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    live_py_module text,
    live_py_class text
);


ALTER TABLE public.strategy_catalog OWNER TO postgres;

--
-- Name: strategy_catalog_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.strategy_catalog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.strategy_catalog_id_seq OWNER TO postgres;

--
-- Name: strategy_catalog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.strategy_catalog_id_seq OWNED BY public.strategy_catalog.id;


--
-- Name: strategy_params; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.strategy_params (
    id integer NOT NULL,
    strategy_id integer NOT NULL,
    name character varying(50) NOT NULL,
    title character varying(100) NOT NULL,
    param_type character varying NOT NULL,
    default_value character varying(100) NOT NULL,
    min_value character varying(100),
    max_value character varying(100),
    step_value character varying(100),
    category_values text,
    description text NOT NULL,
    required smallint DEFAULT 1 NOT NULL
);


ALTER TABLE public.strategy_params OWNER TO postgres;

--
-- Name: strategy_params_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.strategy_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.strategy_params_id_seq OWNER TO postgres;

--
-- Name: strategy_params_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.strategy_params_id_seq OWNED BY public.strategy_params.id;


--
-- Name: strategy_universe; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.strategy_universe (
    id bigint NOT NULL,
    symbol text NOT NULL,
    figi text,
    timeframe text NOT NULL,
    strategy_id text NOT NULL,
    params_json jsonb,
    sharpe double precision,
    max_dd double precision,
    pf double precision,
    trades integer,
    cagr double precision,
    backtest_run_id bigint,
    backtest_started_at timestamp with time zone,
    score double precision,
    grade text,
    enabled boolean DEFAULT false NOT NULL,
    mode text DEFAULT 'backtest'::text NOT NULL,
    priority integer DEFAULT 0 NOT NULL,
    risk_per_trade double precision,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    comment text,
    max_drawdown_fraction double precision DEFAULT 0.2 NOT NULL,
    gap_threshold_fraction double precision DEFAULT 0.2 NOT NULL,
    max_positions_per_strategy integer,
    max_total_positions integer
);


ALTER TABLE public.strategy_universe OWNER TO postgres;

--
-- Name: strategy_universe_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.strategy_universe_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.strategy_universe_id_seq OWNER TO postgres;

--
-- Name: strategy_universe_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.strategy_universe_id_seq OWNED BY public.strategy_universe.id;


--
-- Name: symbols; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.symbols (
    id integer NOT NULL,
    ticker character varying(10) NOT NULL,
    name character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    lot_size integer DEFAULT 1 NOT NULL
);


ALTER TABLE public.symbols OWNER TO postgres;

--
-- Name: symbols_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.symbols_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.symbols_id_seq OWNER TO postgres;

--
-- Name: symbols_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.symbols_id_seq OWNED BY public.symbols.id;


--
-- Name: timeframe_weights; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.timeframe_weights (
    timeframe text NOT NULL,
    tf_weight double precision NOT NULL
);


ALTER TABLE public.timeframe_weights OWNER TO postgres;

--
-- Name: trading_control; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.trading_control (
    id bigint DEFAULT 1 NOT NULL,
    allow_trading boolean DEFAULT true NOT NULL,
    allow_new_positions boolean DEFAULT true NOT NULL,
    comment text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.trading_control OWNER TO postgres;

--
-- Name: backtest_runs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.backtest_runs ALTER COLUMN id SET DEFAULT nextval('public.backtest_runs_id_seq'::regclass);


--
-- Name: bar_state id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bar_state ALTER COLUMN id SET DEFAULT nextval('public.bar_state_id_seq'::regclass);


--
-- Name: live_errors id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_errors ALTER COLUMN id SET DEFAULT nextval('public.live_errors_id_seq'::regclass);


--
-- Name: live_orders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_orders ALTER COLUMN id SET DEFAULT nextval('public.live_orders_id_seq'::regclass);


--
-- Name: live_positions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_positions ALTER COLUMN id SET DEFAULT nextval('public.live_positions_id_seq'::regclass);


--
-- Name: live_signals id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_signals ALTER COLUMN id SET DEFAULT nextval('public.live_signals_id_seq'::regclass);


--
-- Name: live_trades id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_trades ALTER COLUMN id SET DEFAULT nextval('public.live_trades_id_seq'::regclass);


--
-- Name: lot_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lot_history ALTER COLUMN id SET DEFAULT nextval('public.lot_history_id_seq'::regclass);


--
-- Name: optimization_sessions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.optimization_sessions ALTER COLUMN id SET DEFAULT nextval('public.optimization_sessions_id_seq'::regclass);


--
-- Name: strategy_catalog id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_catalog ALTER COLUMN id SET DEFAULT nextval('public.strategy_catalog_id_seq'::regclass);


--
-- Name: strategy_params id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_params ALTER COLUMN id SET DEFAULT nextval('public.strategy_params_id_seq'::regclass);


--
-- Name: strategy_universe id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_universe ALTER COLUMN id SET DEFAULT nextval('public.strategy_universe_id_seq'::regclass);


--
-- Name: symbols id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.symbols ALTER COLUMN id SET DEFAULT nextval('public.symbols_id_seq'::regclass);


--
-- Name: account_state account_state_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.account_state
    ADD CONSTRAINT account_state_pkey PRIMARY KEY (id);


--
-- Name: backtest_runs backtest_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.backtest_runs
    ADD CONSTRAINT backtest_runs_pkey PRIMARY KEY (id);


--
-- Name: bar_state bar_state_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bar_state
    ADD CONSTRAINT bar_state_pkey PRIMARY KEY (id);


--
-- Name: bar_state bar_state_unq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bar_state
    ADD CONSTRAINT bar_state_unq UNIQUE (service_name, timeframe);


--
-- Name: datafeed_state datafeed_state_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.datafeed_state
    ADD CONSTRAINT datafeed_state_pkey PRIMARY KEY (id);


--
-- Name: live_errors live_errors_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_errors
    ADD CONSTRAINT live_errors_pkey PRIMARY KEY (id);


--
-- Name: live_orders live_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_orders
    ADD CONSTRAINT live_orders_pkey PRIMARY KEY (id);


--
-- Name: live_positions live_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_positions
    ADD CONSTRAINT live_positions_pkey PRIMARY KEY (id);


--
-- Name: live_positions live_positions_unq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_positions
    ADD CONSTRAINT live_positions_unq UNIQUE (strategy_universe_id, symbol, timeframe);


--
-- Name: live_signals live_signals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_signals
    ADD CONSTRAINT live_signals_pkey PRIMARY KEY (id);


--
-- Name: live_trades live_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_trades
    ADD CONSTRAINT live_trades_pkey PRIMARY KEY (id);


--
-- Name: lot_history lot_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lot_history
    ADD CONSTRAINT lot_history_pkey PRIMARY KEY (id);


--
-- Name: optimization_sessions optimization_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.optimization_sessions
    ADD CONSTRAINT optimization_sessions_pkey PRIMARY KEY (id);


--
-- Name: service_status service_status_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.service_status
    ADD CONSTRAINT service_status_pkey PRIMARY KEY (service_name);


--
-- Name: strategy_catalog strategy_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_catalog
    ADD CONSTRAINT strategy_catalog_pkey PRIMARY KEY (id);


--
-- Name: strategy_params strategy_params_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_params
    ADD CONSTRAINT strategy_params_pkey PRIMARY KEY (id);


--
-- Name: strategy_universe strategy_universe_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_universe
    ADD CONSTRAINT strategy_universe_pkey PRIMARY KEY (id);


--
-- Name: strategy_universe strategy_universe_uq_symbol_tf_strat; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.strategy_universe
    ADD CONSTRAINT strategy_universe_uq_symbol_tf_strat UNIQUE (symbol, timeframe, strategy_id);


--
-- Name: symbols symbols_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.symbols
    ADD CONSTRAINT symbols_pkey PRIMARY KEY (id);


--
-- Name: timeframe_weights timeframe_weights_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timeframe_weights
    ADD CONSTRAINT timeframe_weights_pkey PRIMARY KEY (timeframe);


--
-- Name: trading_control trading_control_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.trading_control
    ADD CONSTRAINT trading_control_pkey PRIMARY KEY (id);


--
-- Name: code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX code ON public.strategy_catalog USING btree (code);


--
-- Name: idx_candles_15m_is_gap; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_candles_15m_is_gap ON public.candles_15m USING btree (symbol_id, is_gap, "timestamp");


--
-- Name: idx_candles_1d_is_gap; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_candles_1d_is_gap ON public.candles_1d USING btree (symbol_id, is_gap, "timestamp");


--
-- Name: idx_candles_1h_is_gap; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_candles_1h_is_gap ON public.candles_1h USING btree (symbol_id, is_gap, "timestamp");


--
-- Name: idx_candles_30m_is_gap; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_candles_30m_is_gap ON public.candles_30m USING btree (symbol_id, is_gap, "timestamp");


--
-- Name: idx_candles_4h_is_gap; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_candles_4h_is_gap ON public.candles_4h USING btree (symbol_id, is_gap, "timestamp");


--
-- Name: idx_candles_5m_is_gap; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_candles_5m_is_gap ON public.candles_5m USING btree (symbol_id, is_gap, "timestamp");


--
-- Name: idx_live_errors_source_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_errors_source_time ON public.live_errors USING btree (source, "timestamp");


--
-- Name: idx_live_errors_strategy; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_errors_strategy ON public.live_errors USING btree (strategy_universe_id, "timestamp");


--
-- Name: idx_live_errors_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_errors_time ON public.live_errors USING btree ("timestamp");


--
-- Name: idx_live_orders_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_orders_status ON public.live_orders USING btree (status, created_at);


--
-- Name: idx_live_orders_symbol_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_orders_symbol_time ON public.live_orders USING btree (symbol, created_at);


--
-- Name: idx_live_positions_strategy; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_positions_strategy ON public.live_positions USING btree (strategy_universe_id);


--
-- Name: idx_live_positions_symbol_tf; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_positions_symbol_tf ON public.live_positions USING btree (symbol, timeframe);


--
-- Name: idx_live_signals_processed; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_signals_processed ON public.live_signals USING btree (processed, signal_timestamp);


--
-- Name: idx_live_signals_symbol_tf_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_signals_symbol_tf_time ON public.live_signals USING btree (symbol, timeframe, bar_timestamp);


--
-- Name: idx_live_trades_strategy_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_trades_strategy_time ON public.live_trades USING btree (strategy_universe_id, executed_at);


--
-- Name: idx_live_trades_symbol_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_live_trades_symbol_time ON public.live_trades USING btree (symbol, executed_at);


--
-- Name: idx_strategy; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_strategy ON public.strategy_params USING btree (strategy_id);


--
-- Name: ticker; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ticker ON public.symbols USING btree (ticker);


--
-- Name: uk_symbol_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uk_symbol_date ON public.lot_history USING btree (symbol_id, change_date);


--
-- Name: strategy_universe trg_set_timestamp_strategy_universe; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_set_timestamp_strategy_universe BEFORE UPDATE ON public.strategy_universe FOR EACH ROW EXECUTE FUNCTION public.set_timestamp_strategy_universe();


--
-- Name: live_errors live_errors_strategy_universe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_errors
    ADD CONSTRAINT live_errors_strategy_universe_id_fkey FOREIGN KEY (strategy_universe_id) REFERENCES public.strategy_universe(id) ON DELETE SET NULL;


--
-- Name: live_orders live_orders_live_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_orders
    ADD CONSTRAINT live_orders_live_signal_id_fkey FOREIGN KEY (live_signal_id) REFERENCES public.live_signals(id) ON DELETE SET NULL;


--
-- Name: live_orders live_orders_strategy_universe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_orders
    ADD CONSTRAINT live_orders_strategy_universe_id_fkey FOREIGN KEY (strategy_universe_id) REFERENCES public.strategy_universe(id) ON DELETE CASCADE;


--
-- Name: live_positions live_positions_strategy_universe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_positions
    ADD CONSTRAINT live_positions_strategy_universe_id_fkey FOREIGN KEY (strategy_universe_id) REFERENCES public.strategy_universe(id) ON DELETE CASCADE;


--
-- Name: live_signals live_signals_strategy_universe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_signals
    ADD CONSTRAINT live_signals_strategy_universe_id_fkey FOREIGN KEY (strategy_universe_id) REFERENCES public.strategy_universe(id) ON DELETE CASCADE;


--
-- Name: live_trades live_trades_live_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_trades
    ADD CONSTRAINT live_trades_live_order_id_fkey FOREIGN KEY (live_order_id) REFERENCES public.live_orders(id) ON DELETE SET NULL;


--
-- Name: live_trades live_trades_strategy_universe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.live_trades
    ADD CONSTRAINT live_trades_strategy_universe_id_fkey FOREIGN KEY (strategy_universe_id) REFERENCES public.strategy_universe(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict XggjwLegZAvbDbLLwt7vrhcn7ahJxZsqyLz8Q5KJzv2OTL4QwJCY52ARqvjluoB

